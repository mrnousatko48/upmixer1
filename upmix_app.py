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
            "lfe_inverted": False, "crossover": 120, 
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
            rear, center, lfe, boost = 0.0, 0.0, 0.0, 0.0
        else:
            rear = params.get('rear_gain', 0.7)
            center = params.get('center_gain', 0.8)
            lfe = params.get('lfe_gain', 1.0)
            boost = params.get('bass_boost', 0)
            if params.get('lfe_inverted', False):
                lfe = -lfe

        delay_rear = params.get('rear_delay', 0.015)
        delay_lfe = params.get('lfe_delay', 0.0)
        
        try:
            commands = [
                f'"mixFC:Gain 1" {center}', f'"mixFC:Gain 2" {center}',
                f'"mixLFE:Gain 1" {lfe}', f'"mixLFE:Gain 2" {lfe}',
                f'"mixRL:Gain 1" {rear}', f'"mixRR:Gain 1" {rear}',
                f'"delayRL:Delay (s)" {delay_rear}', f'"delayRR:Delay (s)" {delay_rear}',
                f'"delayLFE:Delay (s)" {delay_lfe}', 
                f'"eqBoost:Gain 1" {boost}'
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
