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
SETTINGS_FILE = os.path.expanduser("~/.config/upmixer_settings.json")
SYSTEM_CONFIG_PATH = os.path.expanduser("~/.config/pipewire/pipewire.conf.d/upmix-sink.conf")

CONFIG_TEMPLATE = """
context.modules = [
    {   name = libpipewire-module-filter-chain
        args = {
            node.description = "Upmix Sink"
            node.name = "Upmix_Sink"
            filter.graph = {
                nodes = [
                    { type = builtin name = copyFL label = copy }
                    { type = builtin name = copyFR label = copy }
                    
                    # High-Pass Filters for Main/Center/Rear (Crucial for Bass Clarity)
                    { name = hpFL  type = builtin label = param_eq config = { filters = [ { type = bq_highpass freq = 120 } ] } }
                    { name = hpFR  type = builtin label = param_eq config = { filters = [ { type = bq_highpass freq = 120 } ] } }
                    { name = hpFC  type = builtin label = param_eq config = { filters = [ { type = bq_highpass freq = 120 } ] } }
                    { name = hpRL  type = builtin label = param_eq config = { filters = [ { type = bq_highpass freq = 120 } ] } }
                    { name = hpRR  type = builtin label = param_eq config = { filters = [ { type = bq_highpass freq = 120 } ] } }

                    # Stereo Widener (Mid-Side processing)
                    { name = mixMid   type = builtin label = mixer }
                    { name = mixSide  type = builtin label = mixer control = { "Gain 2" = -1.0 } }
                    { name = outFL    type = builtin label = mixer }
                    { name = outFR    type = builtin label = mixer control = { "Gain 2" = -1.0 } }
                    
                    { name = mixFC    type = builtin label = mixer }
                    { name = mixRL    type = builtin label = mixer }
                    { name = mixRR    type = builtin label = mixer }
                    { name = mixLFE   type = builtin label = mixer }
                    
                    # Routing Stage (for Sub/Center swap)
                    { name = routeFC  type = builtin label = mixer }
                    { name = routeLFE type = builtin label = mixer }
                    
                    {
                        type = builtin
                        name = eqLFE
                        label = param_eq
                        config = {
                            filters = [ 
                                { type = bq_lowpass freq = 120 },
                                { type = bq_lowpass freq = 120 },
                                { type = bq_peaking freq = 35 q = 0.8 gain = 0 },
                                { type = bq_peaking freq = 60 q = 1.0 gain = 0 }
                            ]
                        }
                    }

                    { type = builtin name = delayRL  label = delay config = { "max-delay" = 0.5 } }
                    { type = builtin name = delayRR  label = delay config = { "max-delay" = 0.5 } }
                    { type = builtin name = delayLFE label = delay config = { "max-delay" = 0.1 } }
                ]
                links = [
                    # Stereo Widener Logic
                    { output = "copyFL:Out" input = "mixMid:In 1" }
                    { output = "copyFR:Out" input = "mixMid:In 2" }
                    { output = "copyFL:Out" input = "mixSide:In 1" }
                    { output = "copyFR:Out" input = "mixSide:In 2" }
                    
                    { output = "mixMid:Out"  input = "outFL:In 1" }
                    { output = "mixSide:Out" input = "outFL:In 2" }
                    { output = "mixMid:Out"  input = "outFR:In 1" }
                    { output = "mixSide:Out" input = "outFR:In 2" }

                    # Main Output -> High Pass
                    { output = "outFL:Out"  input = "hpFL:In 1" }
                    { output = "outFR:Out"  input = "hpFR:In 1" }

                    # Surround -> High Pass -> Delay
                    { output = "copyFL:Out" input = "mixRL:In 1" }
                    { output = "copyFR:Out" input = "mixRR:In 1" }
                    { output = "mixRL:Out"  input = "hpRL:In 1" }
                    { output = "mixRR:Out"  input = "hpRR:In 1" }
                    { output = "hpRL:Out 1" input = "delayRL:In" }
                    { output = "hpRR:Out 1" input = "delayRR:In" }
                    
                    # Center -> High Pass
                    { output = "copyFL:Out" input = "mixFC:In 1" }
                    { output = "copyFR:Out" input = "mixFC:In 2" }
                    { output = "mixFC:Out"  input = "hpFC:In 1" }
                    
                    # LFE -> EQ -> Delay
                    { output = "copyFL:Out" input = "mixLFE:In 1" }
                    { output = "copyFR:Out" input = "mixLFE:In 2" }
                    { output = "mixLFE:Out" input = "eqLFE:In 1" }
                    { output = "eqLFE:Out 1" input = "delayLFE:In" }
                    
                    # Final Swap Router
                    { output = "hpFC:Out 1"     input = "routeFC:In 1" }
                    { output = "delayLFE:Out"   input = "routeFC:In 2" }
                    { output = "hpFC:Out 1"     input = "routeLFE:In 1" }
                    { output = "delayLFE:Out"   input = "routeLFE:In 2" }
                ]
                inputs = [ "copyFL:In" "copyFR:In" ]
                outputs = [ 
                    "hpFL:Out 1" "hpFR:Out 1" "routeFC:Out" 
                    "routeLFE:Out" "delayRL:Out" "delayRR:Out" 
                ]
            }
            capture.props = {
                node.name = "Upmix_Sink"
                media.class = "Audio/Sink"
                audio.channels = 2
                audio.position = [ FL FR ]
            }
            playback.props = {
                node.name = "Upmix_Output"
                audio.channels = 6
                audio.position = [ FL FR FC LFE RL RR ]
                node.passive = true
            }
        }
    }
]
"""

class UpmixAPI:
    def __init__(self, app):
        self.app = app

    def toggle_upmixer(self, active, params):
        self.app.is_enabled = active
        self.app.save_settings(params)
        self.app.apply_live_params(params)

    def update_params(self, params):
        self.app.save_settings(params)
        if self.app.is_loaded:
            self.app.apply_live_params(params)

    def get_active_apps(self):
        return self.app.active_streams

    def get_settings(self):
        return self.app.load_settings()

    def install_sink(self):
        return self.app.install_sink()

class UpmixApp:
    def __init__(self):
        self.is_loaded = False
        self.active_streams = []
        self.running = True
        self.is_enabled = True

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    self.is_enabled = settings.get('is_enabled', True)
                    return settings
            except: pass
        return {
            "rear_gain": 0.7, "rear_delay": 0.015,
            "center_gain": 0.8, "lfe_gain": 1.0, 
            "lfe_delay": 0.0, "bass_boost": 0,
            "stereo_width": 1.0, "lfe_inverted": False, 
            "swap_sub_center": False, "crossover": 120, 
            "is_enabled": True
        }

    def save_settings(self, params):
        settings = params.copy()
        settings['is_enabled'] = self.is_enabled
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
        except: pass

    def install_sink(self):
        try:
            os.makedirs(os.path.dirname(SYSTEM_CONFIG_PATH), exist_ok=True)
            with open(SYSTEM_CONFIG_PATH, 'w') as f:
                f.write(CONFIG_TEMPLATE)
            # Restart pipewire
            subprocess.run(["systemctl", "--user", "restart", "pipewire"], check=True)
            return True
        except Exception as e:
            print(f"Install error: {e}")
            return False

    def get_pw_dump(self):
        try:
            result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except: return []

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
                    if props.get("node.name") != UPMIX_SINK_NAME and "alsa" in str(props):
                        return obj.get("id")
        return None

    def apply_live_params(self, params):
        dump = self.get_pw_dump()
        node_id = self.get_node_id_by_name(dump, UPMIX_SINK_NAME)
        if not node_id: return

        if not self.is_enabled:
            rear, center, lfe, boost, width = 0.0, 0.0, 0.0, 0.0, 0.0
        else:
            rear = params.get('rear_gain', 0.7)
            center = params.get('center_gain', 0.8)
            lfe = params.get('lfe_gain', 1.0)
            boost = params.get('bass_boost', 0)
            width = params.get('stereo_width', 1.0)
            if params.get('lfe_inverted', False):
                lfe = -lfe

        delay_rear = params.get('rear_delay', 0.015)
        delay_lfe = params.get('lfe_delay', 0.0)
        swap = params.get('swap_sub_center', False)
        crossover = params.get('crossover', 120)
        
        # X-Bass Params
        
        try:
            commands = [
                f'"mixFC:Gain 1" {center}', f'"mixFC:Gain 2" {center}',
                f'"mixLFE:Gain 1" {lfe}', f'"mixLFE:Gain 2" {lfe}',
                f'"mixRL:Gain 1" {rear}', f'"mixRR:Gain 1" {rear}',
                f'"delayRL:Delay (s)" {delay_rear}', f'"delayRR:Delay (s)" {delay_rear}',
                f'"delayLFE:Delay (s)" {delay_lfe}', 
                f'"eqLFE:Gain 3" {boost}',
                f'"eqLFE:Gain 4" {boost * 0.7}',
                f'"hpFL:Highpass (Hz)" {crossover}',
                f'"hpFR:Highpass (Hz)" {crossover}',
                f'"hpFC:Highpass (Hz)" {crossover}',
                f'"hpRL:Highpass (Hz)" {crossover}',
                f'"hpRR:Highpass (Hz)" {crossover}',
                f'"eqLFE:Lowpass (Hz) 1" {crossover}',
                f'"eqLFE:Lowpass (Hz) 2" {crossover}',
                f'"routeFC:Gain 1" {1.0 if not swap else 0.0}',
                f'"routeFC:Gain 2" {0.0 if not swap else 1.0}',
                f'"routeLFE:Gain 1" {0.0 if not swap else 1.0}',
                f'"routeLFE:Gain 2" {1.0 if not swap else 0.0}',
                f'"outFL:Gain 2" {width}', f'"outFR:Gain 2" {-width}'
            ]
            for cmd in commands:
                subprocess.run(["pw-cli", "s", str(node_id), "Props", f"{{ params = [ {cmd} ] }}"], capture_output=True)
        except: pass

    def get_metadata_targets(self):
        try:
            result = subprocess.run(["pw-metadata", "-n", "default"], capture_output=True, text=True)
            targets = {}
            for line in result.stdout.splitlines():
                if "target.node" in line:
                    parts = line.split()
                    try:
                        n_id, v_id = None, None
                        for part in parts:
                            if part.startswith("id:"): n_id = part[3:]
                            elif part.startswith("value:"): v_id = part[6:].strip("'")
                        if n_id and v_id: targets[n_id] = v_id
                    except: continue
            return targets
        except: return {}

    def ensure_upmixer_linked(self, dump, upmix_output_id, hw_sink_id):
        if not upmix_output_id or not hw_sink_id: return
        targets = self.get_metadata_targets()
        if targets.get(str(upmix_output_id)) != str(hw_sink_id):
            subprocess.run(["pw-metadata", "-n", "default", str(upmix_output_id), "target.node", str(hw_sink_id)])

    def monitor_loop(self):
        last_states = {} 
        while self.running:
            dump = self.get_pw_dump()
            upmix_id = self.get_node_id_by_name(dump, UPMIX_SINK_NAME)
            upmix_output_id = self.get_node_id_by_name(dump, "Upmix_Output")
            hw_sink_id = self.get_hardware_sink_id(dump)
            
            self.ensure_upmixer_linked(dump, upmix_output_id, hw_sink_id)
            metadata_targets = self.get_metadata_targets()

            current_active = []
            for obj in dump:
                if obj.get("type") == "PipeWire:Interface:Node":
                    props = obj.get("info", {}).get("props", {})
                    if props.get("media.class") == "Stream/Output/Audio":
                        node_id = str(obj.get("id"))
                        serial = props.get("object.serial")
                        channels = props.get("audio.channels", 2)
                        
                        if last_states.get(node_id) != serial:
                            target_id = None
                            if channels == 2 and upmix_id:
                                target_id = upmix_id
                            elif channels > 2 and hw_sink_id:
                                target_id = hw_sink_id
                            
                            if target_id:
                                subprocess.run(["pw-metadata", "-n", "default", node_id, "target.node", str(target_id)])
                                last_states[node_id] = serial
                        
                        if metadata_targets.get(node_id) == str(upmix_id):
                             current_active.append({"name": props.get("application.name", "Unknown"), "channels": channels})

            self.active_streams = current_active
            time.sleep(CHECK_INTERVAL)

    def start(self):
        settings = self.load_settings()
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

        ui_path = os.path.join(os.path.dirname(__file__), "ui", "index.html")
        api = UpmixAPI(self)
        window = webview.create_window("Upmix Pro", ui_path, js_api=api, width=450, height=850, resizable=True)
        
        time.sleep(1)
        self.is_loaded = True
        self.apply_live_params(settings)

        webview.start(gui='gtk')
        self.running = False

if __name__ == "__main__":
    app = UpmixApp()
    app.start()
