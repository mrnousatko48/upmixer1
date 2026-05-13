#!/usr/bin/env python3
import webview
import subprocess
import json
import time
import threading
import os
import sys

# Configuration
UPMIX_SINK_NAME = "Upmix_Sink"
CHECK_INTERVAL = 2.0

class UpmixAPI:
    def __init__(self, app):
        self.app = app

    def toggle_upmixer(self, active, params):
        if active:
            self.app.load_upmixer(params)
        else:
            self.app.unload_upmixer()

    def update_params(self, params):
        if self.app.is_loaded:
            self.app.apply_live_params(params)

    def get_active_apps(self):
        return self.app.active_streams

class UpmixApp:
    def __init__(self):
        self.is_loaded = False
        self.active_streams = []
        self.current_params = None
        self.module_id = None
        self.monitor_thread = None
        self.running = True

    def get_pw_dump(self):
        try:
            result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except:
            return []

    def get_node_id_by_name(self, dump, name):
        for obj in dump:
            if obj.get("type") == "PipeWire:Interface:Node":
                props = obj.get("info", {}).get("props", {})
                if props.get("node.name") == name:
                    return obj.get("id")
        return None

    def get_hardware_sink_id(self, dump):
        for obj in dump:
            if obj.get("type") == "PipeWire:Interface:Node":
                props = obj.get("info", {}).get("props", {})
                if props.get("media.class") == "Audio/Sink":
                    # Avoid picking our own sinks or virtual ones
                    if props.get("node.name") != UPMIX_SINK_NAME and "alsa" in str(props):
                        return obj.get("id")
        return None

    def generate_config(self, params):
        rear = params.get('rear_gain', 0.7)
        center = params.get('center_gain', 0.8)
        lfe = params.get('lfe_gain', 1.0)
        cutoff = params.get('crossover', 120)

        # Compact one-line config for pactl
        config = (
            f'{{ node.description="Upmix Sink" node.name="{UPMIX_SINK_NAME}" '
            f'filter.graph={{ nodes=[ '
            f'{{ type=builtin name=copyFL label=copy }} {{ type=builtin name=copyFR label=copy }} '
            f'{{ type=builtin name=copyOFL label=copy }} {{ type=builtin name=copyOFR label=copy }} '
            f'{{ name=mixFC type=builtin label=mixer control={{ "Gain 1"={center} "Gain 2"={center} }} }} '
            f'{{ name=mixLFE type=builtin label=mixer control={{ "Gain 1"={lfe} "Gain 2"={lfe} }} }} '
            f'{{ name=mixRL type=builtin label=mixer control={{ "Gain 1"={rear} }} }} '
            f'{{ name=mixRR type=builtin label=mixer control={{ "Gain 1"={rear} }} }} '
            f'{{ type=builtin name=eqLFE label=param_eq config={{ filters1=[ {{ type=bq_lowpass freq={cutoff} }} ] }} }} '
            f'] links=[ '
            f'{{ output="copyFL:Out" input="copyOFL:In" }} {{ output="copyFR:Out" input="copyOFR:In" }} '
            f'{{ output="copyFL:Out" input="mixFC:In 1" }} {{ output="copyFR:Out" input="mixFC:In 2" }} '
            f'{{ output="copyFL:Out" input="mixLFE:In 1" }} {{ output="copyFR:Out" input="mixLFE:In 2" }} '
            f'{{ output="copyFL:Out" input="mixRL:In 1" }} {{ output="copyFR:Out" input="mixRR:In 1" }} '
            f'{{ output="mixLFE:Out" input="eqLFE:In 1" }} '
            f'] inputs=["copyFL:In" "copyFR:In"] '
            f'outputs=["copyOFL:Out" "copyOFR:Out" "mixFC:Out" "eqLFE:Out 1" "mixRL:Out" "mixRR:Out"] }} '
            f'capture.props={{ node.name="{UPMIX_SINK_NAME}" media.class="Audio/Sink" audio.channels=2 audio.position=[FL FR] }} '
            f'playback.props={{ node.name="Upmix_Output" audio.channels=6 audio.position=[FL FR FC LFE RL RR] node.passive=true }} }}'
        )
        return config

    def load_upmixer(self, params):
        # 1. Adoption Logic: Check if already exists
        dump = self.get_pw_dump()
        upmix_id = self.get_node_id_by_name(dump, UPMIX_SINK_NAME)
        if upmix_id:
            print(f"Adopting existing Upmix Sink (ID: {upmix_id})")
            self.is_loaded = True
            self.apply_live_params(params)
            return

        # 2. Fallback: Try to load via pactl
        config_str = self.generate_config(params)
        for module in ["libpipewire-module-filter-chain", "module-filter-chain"]:
            try:
                cmd = ["pactl", "load-module", module, config_str]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self.module_id = result.stdout.strip()
                self.is_loaded = True
                print(f"Upmixer loaded via {module}")
                return
            except:
                continue
        
        print("Failed to load upmixer. Ensure filter-chain is installed.")

    def apply_live_params(self, params):
        dump = self.get_pw_dump()
        node_id = self.get_node_id_by_name(dump, UPMIX_SINK_NAME)
        if not node_id:
            return

        rear = params.get('rear_gain', 0.7)
        center = params.get('center_gain', 0.8)
        lfe = params.get('lfe_gain', 1.0)
        
        try:
            # Targeted commands for the new upgraded config
            commands = [
                f'"mixFC:Gain 1" {center}',
                f'"mixFC:Gain 2" {center}',
                f'"mixLFE:Gain 1" {lfe}',
                f'"mixLFE:Gain 2" {lfe}',
                f'"mixRL:Gain 1" {rear}',
                f'"mixRR:Gain 1" {rear}'
            ]

            for cmd in commands:
                subprocess.run(["pw-cli", "s", str(node_id), "Props", f"{{ params = [ {cmd} ] }}"], capture_output=True)
            print("Applied live parameters")
        except Exception as e:
            print(f"Live update failed: {e}")

    def get_metadata_targets(self):
        try:
            result = subprocess.run(["pw-metadata", "-n", "default"], capture_output=True, text=True)
            targets = {}
            for line in result.stdout.splitlines():
                if "target.node" in line:
                    # Parse id:113 key:'target.node' value:'37'
                    parts = line.split()
                    try:
                        n_id = parts[2].replace("id:", "")
                        v_id = parts[4].replace("value:", "").replace("'", "")
                        targets[n_id] = v_id
                    except: continue
            return targets
        except:
            return {}

    def unload_upmixer(self):
        if self.module_id:
            subprocess.run(["pactl", "unload-module", self.module_id])
            self.module_id = None
        else:
            # Fallback: find and unload any existing upmix sinks
            subprocess.run(["pactl", "unload-module", "module-pipewire-filter-chain"], stderr=subprocess.DEVNULL)
        
        self.is_loaded = False
        print("Upmixer unloaded")

    def monitor_loop(self):
        moved_serials = {}
        while self.running:
            dump = self.get_pw_dump()
            upmix_id = self.get_node_id_by_name(dump, UPMIX_SINK_NAME)
            
            if upmix_id:
                self.is_loaded = True
            
            hw_sink_id = self.get_hardware_sink_id(dump)
            metadata_targets = self.get_metadata_targets()

            current_active = []
            for obj in dump:
                if obj.get("type") == "PipeWire:Interface:Node":
                    props = obj.get("info", {}).get("props", {})
                    if props.get("media.class") == "Stream/Output/Audio":
                        node_id = str(obj.get("id"))
                        serial = props.get("object.serial")
                        app_name = props.get("application.name", "Unknown")
                        channels = 2
                        if "audio.channels" in props:
                            channels = int(props["audio.channels"])
                        
                        # Use metadata to check if it's currently routed to us
                        is_upmixed = metadata_targets.get(node_id) == str(upmix_id)
                        
                        if moved_serials.get(node_id) != serial:
                            target_id = None
                            if channels == 2 and upmix_id:
                                target_id = upmix_id
                            elif channels > 2 and hw_sink_id:
                                target_id = hw_sink_id
                            
                            if target_id:
                                subprocess.run(["pw-metadata", "-n", "default", node_id, "target.node", str(target_id)])
                                moved_serials[node_id] = serial
                        
                        if is_upmixed:
                             current_active.append({"name": app_name, "channels": channels})

            self.active_streams = current_active
            time.sleep(CHECK_INTERVAL)

    def start(self):
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        # UI
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
        api = UpmixAPI(self)
        window = webview.create_window("Upmix Pro", ui_path, js_api=api, width=450, height=700, resizable=False)
        
        webview.start(gui='gtk')
        self.running = False
        self.unload_upmixer()

if __name__ == "__main__":
    app = UpmixApp()
    app.start()
