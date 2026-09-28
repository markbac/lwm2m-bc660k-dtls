import xml.etree.ElementTree as ET
import os
from typing import Dict, Any, List, Optional

class LwM2MXMLParser:
    """Parses OMA LwM2M XML Object definitions into structured objects."""
    
    @staticmethod
    def parse_xml_string(xml_content: str) -> Dict[str, Any]:
        root = ET.fromstring(xml_content)
        
        # Find <Object> element
        obj_elem = root.find("Object")
        if obj_elem is None:
            raise ValueError("Invalid OMA LwM2M XML: Missing <Object> root element")
            
        name = obj_elem.findtext("Name", "Unknown Object")
        obj_id_str = obj_elem.findtext("ObjectID", "0")
        try:
            object_id = int(obj_id_str)
        except ValueError:
            object_id = 0
            
        description = obj_elem.findtext("Description1", "") or obj_elem.findtext("Description2", "")
        urn = obj_elem.findtext("ObjectURN", f"urn:oma:lwm2m:ext:{object_id}")
        multiple = obj_elem.findtext("MultipleInstances", "Single") == "Multiple"
        mandatory = obj_elem.findtext("Mandatory", "Optional") == "Mandatory"
        
        resources = []
        resources_elem = obj_elem.find("Resources")
        if resources_elem is not None:
            for item in resources_elem.findall("Item"):
                res_id_str = item.get("ID") or item.findtext("ID", "0")
                try:
                    res_id = int(res_id_str)
                except ValueError:
                    res_id = 0
                    
                res_name = item.findtext("Name", f"Resource {res_id}")
                operations = item.findtext("Operations", "R").upper()  # R, W, RW, E
                res_type = item.findtext("Type", "String")  # String, Integer, Float, Boolean, Opaque
                units = item.findtext("Units", "")
                res_desc = item.findtext("Description", "")
                res_mandatory = item.findtext("Mandatory", "Optional") == "Mandatory"
                
                resources.append({
                    "id": res_id,
                    "name": res_name,
                    "operations": operations,
                    "type": res_type,
                    "units": units,
                    "description": res_desc,
                    "mandatory": res_mandatory,
                    "value": LwM2MXMLParser.get_default_value(res_type)
                })
                
        return {
            "object_id": object_id,
            "name": name,
            "description": description,
            "urn": urn,
            "multiple_instances": multiple,
            "mandatory": mandatory,
            "resources": resources
        }

    @staticmethod
    def parse_xml_file(file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return LwM2MXMLParser.parse_xml_string(content)

    @staticmethod
    def get_default_value(value_type: str) -> Any:
        vt = value_type.lower()
        if vt == "integer":
            return 0
        elif vt == "float":
            return 0.0
        elif vt == "boolean":
            return False
        elif vt == "opaque":
            return "0000"
        else:
            return "sample_value"
