import argparse
import os
import sys
import json
import csv
from pathlib import Path
from getter import get_npm_packages
from utils import check_path, get_config
import logging
from datetime import datetime

def analyze_instances(instances_dir, must_support_elements):
    """
    Analyze FHIR bundle instances and count usage of mustSupport elements
    Returns updated must_support_elements with usage counts
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(instances_dir):
        logger.warning(f"Instances directory not found: {instances_dir}")
        # Add zero usage count to all elements
        for element in must_support_elements:
            element['use_count'] = 0
        return must_support_elements
    
    # Initialize usage counts
    for element in must_support_elements:
        element['use_count'] = 0
    
    # Get all JSON files in instances directory
    instances_path = Path(instances_dir)
    json_files = list(instances_path.glob("*.json"))
    
    logger.info(f"Found {len(json_files)} JSON files in instances directory")
    
    for json_file in json_files:
        logger.info(f"Analyzing instance file: {json_file.name}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                bundle_content = json.load(f)
            
            # Extract resources from bundle
            resources = []
            if bundle_content.get('resourceType') == 'Bundle':
                for entry in bundle_content.get('entry', []):
                    if 'resource' in entry:
                        resources.append(entry['resource'])
            else:
                # Single resource file
                resources.append(bundle_content)
            
            logger.info(f"Found {len(resources)} resources in {json_file.name}")
            
            # Check each mustSupport element against all resources
            for element in must_support_elements:
                element_path = element['element_path']
                resource_type = element['structure_definition_type']
                extension_uri = element.get('extension_uri')
                
                for resource in resources:
                    if resource.get('resourceType') == resource_type:
                        if check_element_populated(resource, element_path, extension_uri):
                            element['use_count'] += 1
                            logger.debug(f"Found populated element {element_path} in {resource_type}")
                            
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error processing {json_file}: {e}")
            continue
    
    # Log summary
    populated_elements = [e for e in must_support_elements if e['use_count'] > 0]
    logger.info(f"Found {len(populated_elements)} mustSupport elements with usage across all instances")
    
    return must_support_elements

def check_element_populated(resource, element_path, extension_uri=None):
    """
    Check if a specific FHIR element path is populated in a resource
    Handles nested paths and extensions
    """
    # Remove resource type prefix if present (e.g., "Patient.name" -> "name")
    path_parts = element_path.split('.')
    if len(path_parts) > 1 and path_parts[0] == resource.get('resourceType'):
        path_parts = path_parts[1:]
    
    current_obj = resource
    
    for i, part in enumerate(path_parts):
        if current_obj is None:
            return False
            
        # Handle extension paths (e.g., "extension:statusReason")
        if part.startswith('extension:'):
            extension_name = part.split(':')[1]
            if not isinstance(current_obj, dict):
                return False
            extensions = current_obj.get('extension', [])
            if not isinstance(extensions, list):
                return False
                
            # Look for extension with matching URI (preferred) or slice name
            found_extension = None
            for ext in extensions:
                if isinstance(ext, dict):
                    # First try to match by URI if provided
                    if extension_uri and ext.get('url') == extension_uri:
                        found_extension = ext
                        break
                    # Fall back to matching by slice name or URL ending
                    elif (ext.get('url', '').endswith(extension_name) or 
                          ext.get('sliceName') == extension_name):
                        found_extension = ext
                        break
            
            if found_extension is None:
                return False
            
            current_obj = found_extension
            
        elif part == 'extension':
            # Generic extension check
            if not isinstance(current_obj, dict) or 'extension' not in current_obj:
                return False
            current_obj = current_obj['extension']
            
        else:
            # Regular field access
            if isinstance(current_obj, list):
                # For arrays, check if any item has the field
                found = False
                for item in current_obj:
                    if isinstance(item, dict) and part in item:
                        current_obj = item[part]
                        found = True
                        break
                if not found:
                    return False
            elif isinstance(current_obj, dict):
                if part not in current_obj:
                    return False
                current_obj = current_obj[part]
            else:
                return False
    
    # Check if the final value is populated (not None, empty string, or empty array)
    if current_obj is None:
        return False
    if isinstance(current_obj, str) and current_obj.strip() == '':
        return False
    if isinstance(current_obj, list) and len(current_obj) == 0:
        return False
        
    return True

def parse_structure_definitions(package_paths):
    """
    Parse Structure Definitions from FHIR packages and extract mustSupport elements
    Returns a list of dictionaries with structure definition info and mustSupport elements
    """
    logger = logging.getLogger(__name__)
    must_support_elements = []
    
    for package_path in package_paths:
        logger.info(f"Processing package: {package_path}")
        
        # Look for StructureDefinition files in the package
        package_dir = Path(package_path)
        sd_files = list(package_dir.glob("**/*StructureDefinition*.json"))
        
        # Also check for files in package/package folder structure
        if (package_dir / "package").exists():
            sd_files.extend(list((package_dir / "package").glob("**/*StructureDefinition*.json")))
        
        logger.info(f"Found {len(sd_files)} StructureDefinition files in {package_path}")
        
        for sd_file in sd_files:
            try:
                with open(sd_file, 'r', encoding='utf-8') as f:
                    sd_content = json.load(f)
                
                if sd_content.get('resourceType') != 'StructureDefinition':
                    continue
                    
                sd_name = sd_content.get('name', 'Unknown')
                sd_title = sd_content.get('title', sd_name)
                sd_type = sd_content.get('type', 'Unknown')
                sd_url = sd_content.get('url', '')
                
                logger.info(f"Processing StructureDefinition: {sd_name}")
                
                # Extract mustSupport elements from differential first, then snapshot
                elements = sd_content.get('differential', {}).get('element', [])
                if not elements:
                    elements = sd_content.get('snapshot', {}).get('element', [])
                
                must_support_count = 0
                for element in elements:
                    if element.get('mustSupport', False):
                        element_path = element.get('path', '')
                        element_short = element.get('short', '')
                        
                        # Extract cardinality information
                        min_cardinality = element.get('min', 0)
                        max_cardinality = element.get('max', '1')
                        cardinality = f"{min_cardinality}..{max_cardinality}"
                        
                        # Check if this is an extension with a slice name
                        slice_name = element.get('sliceName')
                        extension_uri = None
                        
                        if 'extension' in element_path and slice_name:
                            # Extract the extension URI from the type.profile array
                            if element.get('type'):
                                for type_def in element['type']:
                                    if type_def.get('code') == 'Extension' and type_def.get('profile'):
                                        extension_uri = type_def['profile'][0]  # Take the first profile URI
                                        break
                            
                            # Format as ResourceType.extension:sliceName
                            base_path = element_path.split('.extension')[0]
                            element_path = f"{base_path}.extension:{slice_name}"
                        
                        must_support_elements.append({
                            'structure_definition_type': sd_type,
                            'profile_name': sd_title,
                            'element_path': element_path,
                            'short_description': element_short,
                            'cardinality': cardinality,
                            'profile_url': sd_url,
                            'extension_uri': extension_uri
                        })
                        must_support_count += 1
                
                if must_support_count > 0:
                    logger.info(f"Found {must_support_count} mustSupport elements in {sd_name}")
                        
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Error processing {sd_file}: {e}")
                continue
    
    return must_support_elements

def write_must_support_tsv(elements, output_path):
    """
    Write mustSupport elements to a TSV file
    """
    logger = logging.getLogger(__name__)
    
    if not elements:
        logger.warning("No mustSupport elements found to write")
        return
    
    tsv_file = os.path.join(output_path, "must_support_elements.tsv")
    
    try:
        with open(tsv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            
            # Write header
            writer.writerow([
                'Resource Type',
                'Profile Name', 
                'Element',
                'Cardinality',
                'Use Count'
            ])
            
            # Write data rows
            for element in elements:
                writer.writerow([
                    element['structure_definition_type'],
                    element['profile_name'],
                    element['element_path'],
                    element['cardinality'],
                    element.get('use_count', 0)
                ])
                
        logger.info(f"Wrote {len(elements)} mustSupport elements to {tsv_file}")
        print(f"mustSupport elements written to: {tsv_file}")
        
    except Exception as e:
        logger.error(f"Error writing TSV file: {e}")
        raise

def main():
    """
    Download a package for an IG or use a local copy if already in existence in the FHIR package cache:
       see config file fhir-package-cache variable for location,  The IG name, version is in an array called packages
    Parse the Structure definitions and note the mustSupport elements
    Write these to a TSV and include 
    Resource Type | Profile name | Element | Cardinality | Short description of element 
       
    Keyword arguments:
    rootdir -- Root data folder, where the report file goes
    config.json tells the download which package to download from simplifier.net
    and which errors/warnings can be safely ignored or checked manually.    
    """
    
    homedir = os.environ['HOME']
    parser = argparse.ArgumentParser(description='Extract mustSupport elements from FHIR Implementation Guide packages')
    defaultpath = os.path.join(homedir, "data", "ms-find")

    logger = logging.getLogger(__name__)
    parser.add_argument("-r", "--rootdir", help="Root data folder", default=defaultpath)   
    args = parser.parse_args()
    
    ## Create the data path if it doesn't exist
    check_path(args.rootdir)

    # setup report output folder for TSV reports   
    outdir = os.path.join(args.rootdir, "reports")
    check_path(outdir)
    
    # setup logs folder
    logs_dir = os.path.join(args.rootdir, "logs")
    check_path(logs_dir)

    ## Setup logging
    now = datetime.now() # current date and time
    ts = now.strftime("%Y%m%d-%H%M%S")
    FORMAT = '%(asctime)s %(lineno)d : %(message)s'
    logging.basicConfig(
        format=FORMAT, 
        filename=os.path.join(logs_dir, f'ms-find-{ts}.log'),
        level=logging.INFO
    )
    logger.info('Started mustSupport element extraction')
    
    config_file = os.path.join(os.getcwd(), 'config', 'config.json')
    
    # Get the initial config
    try:
        conf = get_config(config_file, "init")[0]
        mode = conf.get("mode", "clean")
        logger.info(f'Using mode: {mode}')
    except Exception as e:
        logger.error(f'Error reading config: {e}')
        sys.exit(1)

    # Get FHIR packages from cache or download them
    try:
        npm_path_list = get_npm_packages(mode, data_dir=args.rootdir, config_file=config_file)
        print(f'Successfully retrieved {len(npm_path_list)} FHIR packages')
        logger.info(f'Retrieved {len(npm_path_list)} FHIR packages')
    except Exception as e:
        logger.error(f'Error retrieving FHIR packages: {e}')
        sys.exit(1)

    # Parse Structure Definitions and extract mustSupport elements
    try:
        must_support_elements = parse_structure_definitions(npm_path_list)
        print(f'Found {len(must_support_elements)} mustSupport elements')
        logger.info(f'Extracted {len(must_support_elements)} mustSupport elements')
    except Exception as e:
        logger.error(f'Error parsing Structure Definitions: {e}')
        sys.exit(1)
    
    # Analyze instances directory if it exists
    instances_dir = os.path.join(os.getcwd(), "instances")
    try:
        must_support_elements = analyze_instances(instances_dir, must_support_elements)
        logger.info("Instance analysis completed")
    except Exception as e:
        logger.error(f'Error analyzing instances: {e}')
        # Continue with zero counts if instances analysis fails
        for element in must_support_elements:
            element['use_count'] = 0
    
    # Write mustSupport elements to TSV file
    try:
        write_must_support_tsv(must_support_elements, outdir)
        logger.info("mustSupport element extraction completed successfully")
        print("mustSupport element extraction completed!")
    except Exception as e:
        logger.error(f'Error writing TSV file: {e}')
        sys.exit(1)
    
    logger.info("Finished")

if __name__ == '__main__':
    main()