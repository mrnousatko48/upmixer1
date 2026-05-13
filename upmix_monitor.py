#!/usr/bin/env python3
import subprocess
import json
import time
import sys

# Configuration
UPMIX_SINK_NAME = "Upmix_Sink"
CHECK_INTERVAL = 2.0

def get_pw_dump():
    try:
        result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except:
        return []

def get_node_id_by_name(dump, name):
    for obj in dump:
        if obj.get("type") == "PipeWire:Interface:Node":
            props = obj.get("info", {}).get("props", {})
            if props.get("node.name") == name:
                return obj.get("id")
    return None

def get_hardware_sink_id(dump):
    # Find the primary hardware sink (usually has alsa props and surround class)
    for obj in dump:
        if obj.get("type") == "PipeWire:Interface:Node":
            props = obj.get("info", {}).get("props", {})
            if props.get("media.class") == "Audio/Sink":
                if props.get("node.name") != UPMIX_SINK_NAME and "alsa" in str(props):
                    return obj.get("id")
    return None

def get_stream_channels(obj):
    info = obj.get("info", {})
    props = info.get("props", {})
    if "audio.channels" in props:
        return int(props["audio.channels"])
    params = info.get("params", {})
    if "EnumFormat" in params:
        for fmt in params["EnumFormat"]:
            if isinstance(fmt, dict) and "channels" in fmt:
                return fmt["channels"]
    return 2

def main():
    print("Starting Audio Upmix Monitor...")
    moved_serials = {}

    while True:
        dump = get_pw_dump()
        upmix_id = get_node_id_by_name(dump, UPMIX_SINK_NAME)
        hw_sink_id = get_hardware_sink_id(dump)
        
        if not upmix_id:
            time.sleep(CHECK_INTERVAL)
            continue
            
        for obj in dump:
            if obj.get("type") == "PipeWire:Interface:Node":
                props = obj.get("info", {}).get("props", {})
                if props.get("media.class") == "Stream/Output/Audio":
                    node_id = obj.get("id")
                    serial = props.get("object.serial")
                    
                    if moved_serials.get(node_id) == serial:
                        continue
                        
                    channels = get_stream_channels(obj)
                    app_name = props.get("application.name", "Unknown")
                    
                    target_id = None
                    if channels == 2:
                        target_id = upmix_id
                        print(f"Routing Stereo stream: {app_name} -> Upmix_Sink")
                    elif channels > 2 and hw_sink_id:
                        target_id = hw_sink_id
                        print(f"Routing Surround stream: {app_name} -> Hardware Sink")
                    
                    if target_id:
                        try:
                            subprocess.run(["pw-metadata", "-n", "default", str(node_id), "target.node", str(target_id)], check=True)
                            moved_serials[node_id] = serial
                        except:
                            pass
                            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
