import json
import subprocess
import logging
import shutil
import os
import glob
from utils import get_config
from pathlib import Path

logger = logging.getLogger(__name__)

def get_fhir_packages(mode, data_dir, config_file):
    """
    Get FHIR packages from the local FHIR package cache instead of downloading via npm
    """
    logger.info(f'...getting FHIR package files from local cache using mode {mode}')
    
    # Load package configuration from JSON file
    packages = get_config(config_file, key="packages")
    fhir_cache_path = get_config(config_file, key="fhir-package-cache")
    
    if not fhir_cache_path:
        raise ValueError("fhir-package-cache path not configured in config.json")
    
    if not os.path.exists(fhir_cache_path):
        raise FileNotFoundError(f"FHIR package cache not found at: {fhir_cache_path}")
    
    # Create local package directory for copying packages
    local_packages_path = os.path.join(data_dir, "packages")

    if mode == "clean" and os.path.exists(local_packages_path):
        try:
            shutil.rmtree(local_packages_path)
            logger.info(f'...attempting to remove local packages: {local_packages_path}')
        except Exception as e:
            logger.error(f'Could not remove directory and files in {local_packages_path}: {e}')
    
    if not os.path.exists(local_packages_path):
        os.makedirs(local_packages_path)

    # Create a list of package folder paths to be returned
    path_list = []
    
    # Iterate over FHIR packages in config file
    for standard in packages:
        # Extract name and version from config file
        name = standard['name']
        version = standard['version']
        title = standard['title']

        # Look for the package in the FHIR cache
        package_pattern = f"{name}#{version}"
        cache_package_path = os.path.join(fhir_cache_path, package_pattern)
        
        # Handle version aliases like 'dev' or 'current'
        if not os.path.exists(cache_package_path):
            # Try to find packages that match the name pattern
            matching_packages = glob.glob(os.path.join(fhir_cache_path, f"{name}#*"))
            if version in ['dev', 'current', 'cibuild']:
                # Look for exact match first, then any dev/current version
                for pkg_path in matching_packages:
                    pkg_name = os.path.basename(pkg_path)
                    if pkg_name.endswith(f"#{version}"):
                        cache_package_path = pkg_path
                        break
            
            if not os.path.exists(cache_package_path) and matching_packages:
                # If still not found, use the most recent version
                matching_packages.sort(key=os.path.getmtime, reverse=True)
                cache_package_path = matching_packages[0]
                logger.warning(f"Package {package_pattern} not found, using {os.path.basename(cache_package_path)} instead")

        local_package_path = os.path.join(local_packages_path, f"{name}#{version}")
        
        if not os.path.exists(cache_package_path):
            logger.error(f"Package {package_pattern} not found in FHIR cache at {fhir_cache_path}")
            logger.info(f"Available packages matching {name}: {[os.path.basename(p) for p in glob.glob(os.path.join(fhir_cache_path, f'{name}#*'))]}")
            continue
            
        # Copy package from cache to local directory if not already there
        if not os.path.exists(local_package_path):
            try:
                shutil.copytree(cache_package_path, local_package_path)
                logger.info(f"Copied {title}: {name} ({version}) from FHIR cache")
                print(f"Using cached package {title}: {name} ({version})...")
            except Exception as e:
                logger.error(f"Error copying package {name}: {e}")
                continue
        else:
            logger.info(f'...skipping existing local package for {title}: {name} ({version})...')
        
        path_list.append(local_package_path)
    
    return path_list

# Keep the old function name for backward compatibility
def get_npm_packages(mode, data_dir, config_file):
    """
    Backward compatibility wrapper - now uses FHIR package cache
    """
    return get_fhir_packages(mode, data_dir, config_file)
        
