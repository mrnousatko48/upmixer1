#!/usr/bin/env python3
import subprocess
import json
import time
import psutil
import sys

# Configuration
UPMIX_SINK_NAME = "Upmix_Sink"
CHECK_INTERVAL = 2.0  # Seconds

def get_pw_dump():
    try:
        result = subprocess.run(["pw-dump"], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error running pw-dump: {e}")
        return []

def get_node_id_by_name(dump, name):
    for obj in dump:
        if obj.get("type") == "PipeWire:Interface:Node":
            props = obj.get("info", {}).get("props", {})
            if props.get("node.name") == name:
                return obj.get("id")
    return None

def get_hardware_sink_id(dump):
    # Find a physical hardware sink (usually has alsa props)
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
    
    # Priority 1: audio.channels property
    if "audio.channels" in props:
        return int(props["audio.channels"])
    
    # Priority 2: Inspect Format params
    params = info.get("params", {})
    if "EnumFormat" in params:
        for fmt in params["EnumFormat"]:
            if isinstance(fmt, dict) and "channels" in fmt:
                return fmt["channels"]
    
    return 2 # Default to stereo

def main():
    print("Starting Audio Upmix Monitor...")
    
    # Map of node_id -> object.serial to avoid redundant moves
    moved_serials = {}

    while True:
        dump = get_pw_dump()
        if not dump:
            time.sleep(CHECK_INTERVAL)
            continue
            
        upmix_id = get_node_id_by_name(dump, UPMIX_SINK_NAME)
        hw_sink_id = get_hardware_sink_id(dump)
        
        if not upmix_id:
            # Upmixer not found, maybe wait for it to load
            time.sleep(CHECK_INTERVAL)
            continue
            
        for obj in dump:
            if obj.get("type") == "PipeWire:Interface:Node":
                props = obj.get("info", {}).get("props", {})
                if props.get("media.class") == "Stream/Output/Audio":
                    node_id = obj.get("id")
                    serial = props.get("object.serial")
                    
                    # If we've already handled this specific object instance, skip
                    if moved_serials.get(node_id) == serial:
                        continue
                        
                    channels = get_stream_channels(obj)
                    app_name = props.get("application.name", "Unknown")
                    
                    target_id = None
                    if channels == 2:
                        target_id = upmix_id
                        print(f"Detected Stereo stream: {app_name} (ID:{node_id})")
                    elif channels > 2 and hw_sink_id:
                        target_id = hw_sink_id
                        print(f"Detected Surround stream: {app_name} (ID:{node_id}, {channels} channels)")
                    
                    if target_id:
                        try:
                            print(f"Routing {app_name} ({channels} channels) to target {target_id}...")
                            # Using pw-metadata as a reliable way to set the target node for a stream
                            # This is the modern equivalent of 'moving' a stream
                            subprocess.run(["pw-metadata", "-n", "default", str(node_id), "target.node", str(target_id)], check=True)
                            moved_serials[node_id] = serial
                        except subprocess.CalledProcessError as e:
                            print(f"Failed to route stream {node_id}: {e}")
                            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
