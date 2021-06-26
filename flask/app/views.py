from app import app

from flask import request, jsonify

from sentry_sdk.envelope import Envelope, Item, PayloadRef
import sentry_sdk

import os
import tempfile
import zipfile
import json
import glob

SENTRY_DSN = os.environ.get('SENTRY_DSN')

if not SENTRY_DSN:
    print('set env SENTRY_DSN')
    exit(1)

sentry_sdk.init(
    dsn=SENTRY_DSN,
    default_integrations=False
)

@app.route('/')
def index():
    return "alive"

@app.route('/api/getInfo', methods=['POST'])
def post_get_info():
    return jsonify({
        'needSendReport': True,
        'userMessage': '',
        'dumpType': 1
    })

@app.route('/api/pushReport', methods=['POST'])
def post_push_report():

    if 'report' not in request.files:
        os.abort(400)

    file = request.files['report']
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        extract_report(file, tmp_dir)
        report = read_report(tmp_dir)
        sentry_capture_report(report, tmp_dir)

    return '', 200

def extract_report(file, path_to):
    zip_file_path = os.path.join(path_to, 'report.zip')
    file.save(zip_file_path)

    with zipfile.ZipFile(zip_file_path) as zf:
        zf.extractall(path_to)
    
    os.remove(zip_file_path)

def read_report(path):
    report = {}
    report_file = os.path.join(path, 'report.json')
    with open(report_file) as json_data:
        report = json.load(json_data)
    return report

def sentry_capture_report(report, path_to_attachment):

    with sentry_sdk.configure_scope() as scope:
        
        sentry_sdk.set_level("error")
        
        for file in glob.glob(os.path.join(path_to_attachment, '*')):
            scope.add_attachment(path=file)

        type, value, module, stacktrace = parse_exception(report)
        user_id, user_name = parse_user(report)

        sentry_sdk.set_context('device', {
            'family': 'Desktop',
            'arch': parse_arch(report),
            'name': report['clientInfo']['systemInfo']['clientID'],
            'manufacturer': report['clientInfo']['systemInfo']['processor'],
            'memory_size': report['clientInfo']['systemInfo']['fullRAM'],
            'free_memory': report['clientInfo']['systemInfo']['freeRAM'],
        })
        sentry_sdk.set_context('os', {
            'name': parse_os_name(report),
            'version': parse_os_version(report)
        })
        sentry_sdk.set_context('runtime', {
            'name': report['clientInfo']['appName'],
            'version': report['serverInfo']['appVersion']
        })
        sentry_sdk.set_context('app', {
            'app_identifier': report['configInfo']['name'],
            'app_name': report['configInfo']['description'],
            'app_version': report['configInfo']['version'],
            'app_build': report['configInfo']['hash']
        })

        sentry_sdk.set_user({
            'id': user_id,
            'username': user_name
        })
        
        sentry_sdk.set_extra('CompatibilityMode', report['configInfo']['compatibilityMode'])
        sentry_sdk.set_extra('ChangeEnabled', report['configInfo']['changeEnabled'])
        sentry_sdk.set_extra('DBMS', report['serverInfo']['dbms'])
        sentry_sdk.set_extra('ServerType', report['serverInfo']['type'])
        sentry_sdk.set_extra('ConfigurationInterfaceLanguageCode', report['sessionInfo']['configurationInterfaceLanguageCode'])
        sentry_sdk.set_extra('PlatformInterfaceLanguageCode', report['sessionInfo']['platformInterfaceLanguageCode'])
        sentry_sdk.set_extra('LocaleCode', report['sessionInfo']['localeCode'])
        sentry_sdk.set_extra('InfoBaseLocaleCode', report['infoBaseInfo']['localeCode'])
        sentry_sdk.set_extra('DataSeparation', report['sessionInfo']['dataSeparation'])
        
        parse_event_log(report)

        if stacktrace:
            exeption = {
                'type': type,
                'value': value,
                'module': module,
                'stacktrace': stacktrace
            }
        else:
            exeption = {
                'type': type,
                'value': value,
                'module': module,
            }

        event = {
            'exception': {
                'values': [exeption]
            },
            'release':  report['configInfo']['version'],
            'timestamp': report['time'], 
            'sdk': {
                'name': 'sentry.bsl',
                'version': '0.0.1'
            },
            'platform': 'Other'
        }
        sentry_sdk.capture_event(event)

        user_feedback = report['errorInfo'].get('userDescription')

        if user_feedback:
            capture_user_feedback(sentry_sdk.last_event_id(), user_name, user_feedback)

    sentry_sdk.flush()


def parse_exception(report):
    
    stacktrace = parse_stacktrace(report)
    errors = report['errorInfo']['applicationErrorInfo'].get('errors')

    if not errors:
        return 'UndefinedError', '<Exception text is missing>', '', stacktrace

    error = errors[0]
    error_text = error[0]
    error_types = error[1]
    error_presentation_parts = error_text.split(':')
    if len(error_presentation_parts) == 2:
        error_module = error_presentation_parts[0]\
            .replace('{', '')\
            .replace('}', '')
        error_presentation = error_presentation_parts[1]
    elif len(error_presentation_parts) == 2:
        error_module = ''
        error_presentation = error_presentation_parts[0]
    else:
        error_module = ''
        error_presentation = '<Exception text is missing>'

    error_type = ', '.join(error_types)
    
    return error_type, error_presentation, error_module, stacktrace

def parse_stacktrace(report):
    stack = report['errorInfo']['applicationErrorInfo'].get('stack')
    if not stack:
        return None
    frames = []
    for frame in stack:
        frames.append({
            'in_app': True,
            'function': frame[0],
            'lineno': frame[1],
            'context_line': frame[2]
        })
    return { 'frames': frames }

def parse_arch(report):
    platform_type = report['clientInfo']['platformType']
    return 'x86' if platform_type.endswith('x86') else 'x86_64'

def parse_os_name(report):
    platform_type = report['clientInfo']['platformType'].lower()
    if platform_type.startswith('windows'):
        return 'Windows'
    elif platform_type.startswith('macos'):
        return 'macOS'
    elif platform_type.startswith('linux'):
        return 'Linux'
    else:
        return 'Unknown'

def parse_os_version(report):
    # 'osVersion': "Microsoft Windows 10 version 10.0  (Build 19042)"
	# > 10.0.19041
    # 'osVersion' : "Microsoft Windows 8.1 version 6.3  (Build 9600)"
    # > 6.3.9600
    os_version = report['clientInfo']['systemInfo']['osVersion']\
        .lower()\
        .replace('microsoft', '')\
        .replace('windows 10', '')\
        .replace('windows 8.1', '')\
        .replace('version', '')\
        .replace('build', '.')\
        .replace('(', '')\
        .replace(')', '')\
        .replace(' ', '')
    
    return os_version

def parse_user(report):
    user_name = report['sessionInfo'].get('userName')
    data_sep = report['sessionInfo']['dataSeparation']

    if not user_name:
        user_name = '<Undefined>'

    user_id = user_name
    if data_sep:
        user_id += data_sep
    
    return user_id, user_name

def parse_event_log(report):
    additional_data = report.get('additionalData')
    if not additional_data:
        return
    event_log = additional_data.get('EventLog')
    if not event_log:
        return
    
    for event in event_log:
        if event['Level'] == 'Error':
            level = 'error'
        else:
            level = 'info'

        message = ''
        message = f"Event: {event['EventName']}"
        if event['Meta']:
            message += f"\nMeta:  {event['Meta']}"
        if event['Data']:
            message += f"\nData:  {event['Data']}"
        if event['Comment']:
            message += f"\nComment:\n{event['Comment']}"

        sentry_sdk.add_breadcrumb(
            category='log',
            message=message,
            level=level,
            timestamp=event['Date']
        )

def capture_user_feedback(event_id, user_name, user_feedback):
    # https://develop.sentry.dev/sdk/envelopes/#user-feedback
    
    envelope = Envelope(
        headers={
            "event_id": event_id
        }
    )
    event = {
        'event_id': event_id,
        'name': user_name,
        'comments': user_feedback
    }
    envelope.add_item(Item(payload=PayloadRef(json=event), type="user_report"))

    sentry_sdk.Hub.current.client.transport.capture_envelope(envelope)
