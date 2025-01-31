from miditok import Structured, TokenizerConfig
import boto3
import logging
from botocore.exceptions import ClientError
from datetime import datetime
import asyncio
import os
import json

loop = asyncio.get_event_loop()
# from_path = '/tmp/midi-sequence.mid'

def get_file_size(file_path):
    return os.path.getsize(file_path)

def open_file(file_path):
    with open(file_path, 'rb') as file:
        content = file.read()
    return content

def upload_to_s3(from_path, to_path):
    bucket_name = 'midi-archive'
    # current_date = datetime.now().date()
    # to_path = f'neural-net/{current_date}_sequence.mid'

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html
        response = s3_client.upload_file(from_path, bucket_name, to_path)
    except ClientError as e:
        logging.error(e)
        return False
    return True

# TO DO: export tokenizer along with model, instead of copying over here
def load_tokenizer():
    TOKENIZER_PARAMS = {
        "pitch_range": (21, 109),
        "beat_res": {(0, 4): 8, (4, 12): 4},
        "num_velocities": 4,
        # "special_tokens": ["PAD", "BOS", "EOS", "MASK"],
        "use_chords": True,
        "use_rests": True,
        "use_tempos": True,
        "use_time_signatures": False,
        # "use_programs": False,
        "num_tempos": 4,  # nb of tempo bins
        "tempo_range": (40, 250),  # (min, max),
        "one_token_stream": True,
        "one_token_stream_for_programs": True,
        "use_programs": True
    }
    config = TokenizerConfig(**TOKENIZER_PARAMS)
    
    tokenizer = Structured(config)
    return tokenizer

def save_tokens_to_json(tokens, filepath):
    with open(filepath, "w") as f:
        json.dump(tokens, f)   
    
def save_tokens_to_midi(tokens, filepath):
    tokenizer = load_tokenizer()
    result = tokenizer(tokens)
    result.dump(filepath)

def lambda_handler(event, context):
    midi_filepath = '/tmp/midi-sequence.mid'
    json_filepath = '/tmp/midi-sequence.json'
    tokens = event["body"]
    save_tokens_to_midi(tokens, midi_filepath)
    save_tokens_to_json(tokens, json_filepath)
    
    size = get_file_size(midi_filepath)
    print(f'The size of the file is {size} bytes')
    if size < 50:
        # didn't generate a viable MIDI file
        logging.error('did not generate a viable MIDI file')
        
        return {
            'statusCode': 400,
            'body': 'could not generate a viable MIDI file'
        }

    current_date = datetime.now().date()
    # this version will get over-written daily
    upload_to_s3(midi_filepath, 'neural-net/model-prediction.mid')
    # this one will be archived
    upload_to_s3(midi_filepath, f'neural-net/{current_date}_sequence.mid')
    # this sequence will be used to prompt subsequent token generation
    upload_to_s3(json_filepath, f'neural-net/token_sequence.json')

    return {
        'statusCode': 200,
        'body': 'MIDI generated by the MIDI Archive neural net has been saved to S3 <3'
    }