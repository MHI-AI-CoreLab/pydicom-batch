import yaml
from scu import process_request_batch
from scp import SCP
import os
import sys

def merge_configs(config, operation):
    """Merge common config with operation-specific config"""
    merged = {
        'pacs': config['common']['pacs'],
        'local': config['common']['local'],
        'schedule': config['common']['schedule'],
        'request': {
            'type': operation,
            **config[operation]
        }
    }
    
    # Handle output settings
    merged['output'] = {}
    # If common has output settings, use them as base
    if 'output' in config['common']:
        merged['output'].update(config['common']['output'])
    # Override/add operation-specific output settings
    if 'output' in config[operation]:
        merged['output'].update(config[operation]['output'])
        
    # Add anonymization settings for c-move if they exist
    if operation == 'c-move' and 'anonymization' in config[operation]:
        merged['anonymization'] = config[operation]['anonymization']
        
    return merged

def pydicombatch(config_file, operation):
    with open(config_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
        
        # Merge common config with operation-specific config
        merged_config = merge_configs(config, operation)
        
        print('Running {} extraction defined in: {}'.format(operation, config_file))

        if operation == 'c-move':
            scp = SCP(merged_config)
            scp.start_server()
        try:
            process_request_batch(merged_config)
        except KeyboardInterrupt:
            print('\b\b\r')
            print('\nExtraction stopped. To resume extraction, please re-execute the script.')
            if operation == 'c-move':
                scp.stop_server()

            # For c-move, use the output directory for failed requests
            # For c-find, use the directory of the database file
            if operation == 'c-move':
                failed_dir = merged_config['output']['directory']
            else:
                failed_dir = os.path.dirname(merged_config['output']['database_file'])
                
            filepath_requests_failed = os.path.join(failed_dir, 'requests.failed')
            if os.path.exists(filepath_requests_failed):
                print('Failed requests detected. To re-try failed request, re-run batch request.')
            sys.exit(0)