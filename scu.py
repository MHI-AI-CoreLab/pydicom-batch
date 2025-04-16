import sys
from pynetdicom import AE
from pynetdicom.apps.common import ElementPath
from pydicom.dataset import Dataset
import os.path
import csv
import time
import datetime
import pytz
import signal
import tqdm
import concurrent.futures
import numpy as np
import inquirer
import ast

from pynetdicom import (
    AE, QueryRetrievePresentationContexts
)

from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove
)

continue_extraction = True

def sigint_handler(signal, frame):
    global continue_extraction
    continue_extraction = False
    raise KeyboardInterrupt

def watch_sigint():
    signal.signal(signal.SIGINT, sigint_handler)


class hashabledict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

def dataset_to_csv(ds, filepath, fieldnames):
    write_dict = {}
    for key in fieldnames:
        write_dict[key] = str(ds[key].value)

    dict_to_csv(write_dict, filepath, fieldnames)

def request_from_csv(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = []
            for row in reader:
                rows.append(hashabledict(row))
        return rows
    else:
        return []

def dict_to_csv(write_dict, filepath, fieldnames):
    if os.path.exists(filepath):
        with open(filepath, 'a', newline='', ) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames), dialect='excel')
            writer.writerow(write_dict)
    else:
        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=sorted(fieldnames), dialect='excel')
            writer.writeheader()
            writer.writerow(write_dict)

def add_element_to_list(element_list, key, value):
    if [x if ((x.partition('=')[0] == key) or (x == key)) else None for x in element_list]:
        return [f'{key}={value}' if ((x.partition('=')[0] == key) or (x == key)) else x for x in element_list]
    else:
        element_list.append(f'{key}={value}')
        return element_list

def create_dataset(request):
    ds = Dataset()
    try:
        elements = [ElementPath(path) for path in request['elements']]
        for elem in elements:
            ds = elem.update(ds)
    except Exception as exc:
        raise exc
    return ds

def split_date_range(date_range):
    """Split a date range string (YYYYMMDD-YYYYMMDD) into 5-day intervals"""
    if not date_range or '-' not in date_range:
        return [date_range]
        
    start_date_str, end_date_str = date_range.split('-')
    start_date = datetime.datetime.strptime(start_date_str, '%Y%m%d')
    end_date = datetime.datetime.strptime(end_date_str, '%Y%m%d')
    
    date_ranges = []
    current_date = start_date
    while current_date <= end_date:
        # Get the date 5 days from current date
        next_period = current_date + datetime.timedelta(days=5)
            
        # Adjust end date to be either end of current 5-day period or final end date
        period_end_date = min(next_period - datetime.timedelta(days=1), end_date)
        
        date_range_str = f"{current_date.strftime('%Y%m%d')}-{period_end_date.strftime('%Y%m%d')}"
        date_ranges.append(date_range_str)
        
        current_date = next_period
        
    return date_ranges

def create_requests(config):
    requests = []
    if 'elements_batch_file' in config['request']:
        if os.path.exists(config['request']['elements_batch_file']):
            with open(config['request']['elements_batch_file'], newline='') as csvfile:
                reader = csv.DictReader(csvfile, dialect='excel')
                for row in reader:
                    row_request = config['request'].copy()
                    for key in row:
                        row_request['elements'] = add_element_to_list(row_request['elements'], key, row[key])
                    row_request['elements'] = sorted(row_request['elements'])
                    requests.append(row_request)
        else:
            requests.append(config['request'])
    else:
        # Find StudyDate element and split into weekly intervals if present
        study_date_element = None
        for element in config['request']['elements']:
            if element.startswith('StudyDate='):
                study_date_element = element
                break
                
        if study_date_element:
            date_range = study_date_element.split('=')[1]
            date_ranges = split_date_range(date_range)
            
            # Create a request for each weekly interval
            for weekly_range in date_ranges:
                weekly_request = config['request'].copy()
                weekly_request['elements'] = weekly_request['elements'].copy()
                
                # Replace the StudyDate element with the weekly range
                weekly_request['elements'] = [
                    f"StudyDate={weekly_range}" if e.startswith('StudyDate=') else e 
                    for e in weekly_request['elements']
                ]
                requests.append(weekly_request)
        else:
            requests.append(config['request'])

    filepath_requests = os.path.join(config['output']['directory'], 'requests.whole')
    filepath_requests_completed = os.path.join(config['output']['directory'], 'requests.completed')
    filepath_requests_failed = os.path.join(config['output']['directory'], 'requests.failed')
    if os.path.exists(filepath_requests):
        os.remove(filepath_requests)
    if os.path.exists(filepath_requests_completed):
        os.remove(filepath_requests_completed)
    if os.path.exists(filepath_requests_failed):
        os.remove(filepath_requests_failed)

    for request in requests:
        dict_to_csv(request, filepath_requests, request.keys())

    return requests

def pending_requests(config):
    """
    Returns pending requests to enable resuming
    """
    filepath_requests = os.path.join(config['output']['directory'], 'requests.whole')
    filepath_requests_completed = os.path.join(config['output']['directory'], 'requests.completed')

    reqs1 = request_from_csv(filepath_requests)
    reqs2 = []
    if os.path.isfile(filepath_requests_completed):
        reqs2 = request_from_csv(filepath_requests_completed)

    requests = list(set(reqs1) - set(reqs2))
    for request in requests:
        request['elements'] = list(sorted(ast.literal_eval(request['elements'])))
        request['throttle_time'] = float(request['throttle_time'])
        request['threads'] = int(request['threads'])
    
    questions = []
    if requests:
        questions = [
        inquirer.List('resume',
                        message="A partial extraction was detected. Do you want to resume or overwrite?",
                        choices=['Resume', 'Overwrite'],
                    ),
        ]
    else:
        questions = [
        inquirer.List('resume',
                        message="A completed extraction was detected. Do you want to overwrite?",
                        choices=['Cancel', 'Overwrite'],
                    ),
        ]

    answers = inquirer.prompt(questions)
    if answers['resume'] == 'Overwrite':
        requests = create_requests(config)
    return requests

def failed_requests(config):
    """
    Returns failed requests to enable re-trying
    """
    filepath_requests_failed = os.path.join(config['output']['directory'], 'requests.failed')

    questions = [
    inquirer.List('failed',
                    message="Failed requests from a previous extraction were detected. Do you want to re-try the failed requests?",
                    choices=['Re-try failed requests', 'Remove failed requests'],
                ),
    ]
    answers = inquirer.prompt(questions)

    requests = []
    if answers['failed'] == 'Remove failed requests':
        requests = pending_requests(config)
    else:
        reqs1 = request_from_csv(filepath_requests_failed)
        requests = list(set(reqs1))
        for request in requests:
            request['elements'] = list(sorted(ast.literal_eval(request['elements'])))
            request['throttle_time'] = float(request['throttle_time'])
            request['threads'] = int(request['threads'])
    
    if os.path.exists(filepath_requests_failed):
        os.remove(filepath_requests_failed)
    
    return requests

def thread_scu_function(config, pbar, requests):
    scu = SCU(config)
    scu.pbar = pbar
    scu.process_requests_batch(list(requests))
    return

def process_request_batch(config):

    requests = []
    filepath_requests = os.path.join(config['output']['directory'], 'requests.whole')
    filepath_requests_completed = os.path.join(config['output']['directory'], 'requests.completed')
    filepath_requests_failed = os.path.join(config['output']['directory'], 'requests.failed')

    if (os.path.isfile(filepath_requests)):
        # Previous extraction detected
        if os.path.isfile(filepath_requests_failed):
            # Failed requests detected
            requests = failed_requests(config)
        else:
            # No failed requests detected, return pending requests
            requests = pending_requests(config)
    else:
        # No previous extraction detected
        requests = create_requests(config)
    
    if requests:
        watch_sigint()
        split_requests = np.array_split(requests, config['request']['threads'])
        print('To stop extraction, press CTRL-C. Extraction can be resumed at a later time.')
        pbar = tqdm.tqdm(total=len(requests), 
            desc='Sending {} requests '.format(config['request']['type']), 
            unit='rqst')
        fn = lambda x : thread_scu_function(config, pbar, x)
        if config['request']['threads'] > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=config['request']['threads']) as executor:
                executor.map(fn, split_requests)
        else:
            fn(split_requests[0])
        pbar.close()
    else:
        print('No further requests pending')


def seconds_until(time_str, tzname):
    """
    Returns the number of seconds from now until the time in format HH:mm
    """
    
    list_time_str = time_str.split(':')
    

    h = int(list_time_str[0])
    m = int(list_time_str[1])
    tz = pytz.timezone(tzname)
    now = datetime.datetime.now(tz=tz)
    return int((datetime.timedelta(hours=24) 
        - (now - now.replace(hour=h, minute=m, second=0, microsecond=0)))
        .total_seconds() % (24 * 3600))

class SCU(object):
    """ SCU class
    This class is used to send batches of DIMSE requests (c-find, c-echo, c-move) to a remote SCP
    """
    def __init__(self, config):
        self.config = config
        self.ae = self.create_ae()
        self.query_model = self.create_query_model()
        self.pbar = None
        
    def create_ae(self):
        # Create application entity
        ae = AE(ae_title=self.config['local']['aet'])

        # Set timeouts
        ae.acse_timeout = 300
        ae.dimse_timeout = 300
        ae.network_timeout = 300

        # Set the Presentation Contexts we are requesting the Find SCP support
        if self.config['request']['type'].lower() == 'c-find':
            ae.requested_contexts = QueryRetrievePresentationContexts
                
        elif self.config['request']['type'].lower() == 'c-echo':
            ae.requested_contexts = [VerificationSOPClass]

        elif self.config['request']['type'].lower() == 'c-move':
            ae.requested_contexts = QueryRetrievePresentationContexts

        return ae

    def establish_association(self):
        return self.ae.associate(self.config['pacs']['hostname'], 
            self.config['pacs']['port'],  
            ae_title=self.config['pacs']['aet'],
            max_pdu=16382)

    def wait_until_scheduled_time(self):
        
        if 'schedule' in self.config:
            if self.config['schedule']['enabled']:
                sec_until_start = seconds_until(self.config['schedule']['start_time'], self.config['schedule']['timezone'])
                sec_until_end = seconds_until(self.config['schedule']['end_time'], self.config['schedule']['timezone'])
    
                if sec_until_end > sec_until_start:
                    if self.pbar:
                        self.pbar.set_description('Extraction PAUSED (will resume at {})'.format(self.config['schedule']['start_time']))
                    time.sleep(sec_until_start)
                else:
                    if self.pbar:
                        self.pbar.set_description('Sending {} requests (will pause at {})'.format(self.config['request']['type'], self.config['schedule']['end_time']))
                    

    def retry_association(self):

        for i in range(100):
            if not self.association.is_established:
                time.sleep(1)
                print('Re-trying association')
                self.association = self.establish_association()
            else:
                return
        
        sys.exit(1)


    def create_query_model(self):
        request = self.config['request']
        query_model = None
        if request['type'].lower() == 'c-find':
            if request['model'] == 'study':
                query_model = StudyRootQueryRetrieveInformationModelFind
            elif self.config['request']['model'] == 'psonly':
                query_model = PatientStudyOnlyQueryRetrieveInformationModelFind
            else:
                query_model = PatientRootQueryRetrieveInformationModelFind
        elif request['type'].lower() == 'c-move':
            if request['model'] == 'study':
                query_model = StudyRootQueryRetrieveInformationModelMove
            elif self.config['request']['model'] == 'psonly':
                query_model = PatientStudyOnlyQueryRetrieveInformationModelMove
            else:
                query_model = PatientRootQueryRetrieveInformationModelMove
        return query_model

    def process_requests_batch(self, requests):
        global continue_extraction

        self.association = self.establish_association()
        for request in requests:
            if continue_extraction:
                self.wait_until_scheduled_time()
                self.process_request(request)
                time.sleep(request['throttle_time'])
        self.association.release()
        
    
    def process_request(self, request):
        if request['type'].lower() == 'c-find':
            self.send_find(request)
        if request['type'].lower() == 'c-move':
            self.send_move(request)
        return
    
    
    def send_find(self, request):
        
        identifier = create_dataset(request)
    
        keywords = [ElementPath(path).keyword for path in request['elements']]

        if not self.association.is_established:
            self.retry_association()
        
        if self.association.is_established:
            responses = self.association.send_c_find(identifier, self.query_model)
            response_count = 0
                    
            for (status, rsp_identifier) in responses:
                if status and status.Status in [0xFF00, 0xFF01]:
                    # Status pending
                    response_count += 1
                    # Apply description filters if enabled
                    should_save = True
                    if 'description_filter' in self.config['request'] and self.config['request']['description_filter']['enabled']:
                        should_save = False
                        # Check study description filter
                        if self.config['request']['description_filter']['study_description'] and 'StudyDescription' in rsp_identifier:
                            study_desc = str(rsp_identifier.StudyDescription).upper()
                            for filter_str in self.config['request']['description_filter']['study_description']:
                                if filter_str.upper() in study_desc:
                                    should_save = True
                                    break
                        
                        # Check series description filter if at SERIES level
                        if (not should_save and 
                            self.config['request']['description_filter']['series_description'] and 
                            'SeriesDescription' in rsp_identifier and
                            'QueryRetrieveLevel' in rsp_identifier and
                            rsp_identifier.QueryRetrieveLevel == 'SERIES'):
                            series_desc = str(rsp_identifier.SeriesDescription).upper()
                            for filter_str in self.config['request']['description_filter']['series_description']:
                                if filter_str.upper() in series_desc:
                                    should_save = True
                                    break
                    
                    if should_save:
                        path = os.path.join(self.config['output']['directory'], self.config['output']['database_file'])
                        dataset_to_csv(rsp_identifier, path, keywords)
                else:
                    if self.pbar:
                        self.pbar.update(1)
                    # Status Success, Warning, Cancel, Failure
                    if status.Status in [0x0000]:
                        if response_count > 4500:
                            study_date = next((elem.split('=')[1] for elem in request['elements'] if elem.startswith('StudyDate=')), None)
                            print(f"\nWARNING: Large response count ({response_count}) for date range {study_date}. Consider using smaller date ranges (Limit is 5000).")
                        filepath_requests_completed = os.path.join(self.config['output']['directory'], 'requests.completed')
                        dict_to_csv(request, filepath_requests_completed, request.keys())
                    else:
                        filepath_requests_failed = os.path.join(self.config['output']['directory'], 'requests.failed')
                        dict_to_csv(request, filepath_requests_failed, request.keys())
                
                    

    def send_move(self, request):
        
        identifier = create_dataset(request)
    
        keywords = [ElementPath(path).keyword for path in request['elements']]

        if not self.association.is_established:
            self.retry_association()
        
        if self.association.is_established:
            responses = self.association.send_c_move(identifier, self.config['local']['aet'], self.query_model)
            # print(self.config)
            # print(self.query_model)
            try:
                for (status, rsp_identifier) in responses:
                    # print(status)
                    # print(rsp_identifier)
                    if status and status.Status in [0xFF00]:
                        # Status pending
                        pass
                    else:
                        # Status Success, Warning, Cancel, Failure
                        if self.pbar:
                            self.pbar.update(1)
                        identifier.Status = hex(status.Status)
                        keywords.append('Status')
                        path = os.path.join(self.config['output']['directory'], self.config['output']['database_file'])
                        dataset_to_csv(identifier, path, keywords)

                        if status.Status in [0x0000]:
                            filepath_requests_completed = os.path.join(self.config['output']['directory'], 'requests.completed')
                            dict_to_csv(request, filepath_requests_completed, request.keys())
                        else:
                            filepath_requests_failed = os.path.join(self.config['output']['directory'], 'requests.failed')
                            dict_to_csv(request, filepath_requests_failed, request.keys())
            except Exception as e:
                print(f"Error processing C-MOVE: {str(e)}")




