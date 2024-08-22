import requests
import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from postgrest.exceptions import APIError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import openai
from openai import OpenAI

load_dotenv()

url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
youtube_key = os.getenv('YOUTUBE_KEY')
supabase: Client = create_client(url, supabase_key)
youtube = build('youtube', 'v3', developerKey=youtube_key)  # resource object to interact w/ API
formatter = TextFormatter()
openai_key = os.getenv('OPENAI_KEY')

def get_youtube_video_details(video_ids):
    youtube_details = []
    
    try:
        # retrieve relevant category video info
        # snippet contains basic details about the video
        response = youtube.videos().list(part='id,snippet,contentDetails,statistics', id=','.join(video_ids)).execute()  # API call to get other info about given youtube video
        for item in response['items']:
            transcript = YouTubeTranscriptApi.get_transcript(item['id'])
            formatted_transcript = formatter.format_transcript(transcript)
            print("This is transcript" + formatted_transcript)
            details = {
                'video_id': item['id'],
                'title': item['snippet']['title'],
                'channel_id': item['snippet']['channelId'],
                'tags': item['snippet']['tags'],
                'transcript': transcript,
                'category_id': item['snippet']['categoryId']
            }
            youtube_details.append(details)
        print(f"Query successful")
    except HttpError as e:
        print(f"An HTTP error occurred: {e.resp.status} - {e.content}")
    
    return youtube_details
    

def insert_into_supabase(data):
    for video in data:
        print("L43: Starting new video insert")
        try:
            response = supabase.table('videos').insert(video).execute()
            # if response.error:
            #     print(f"Error inserting video {video['video_id']}: {response.error}")
            # else:
            print(f"Inserted video {video['video_id']} successfully")
        except APIError as e:
            # Log the error message to the console
            print(f"APIError: {e.message}")  

def rate_videos(video_ids):
    client = OpenAI(api_key=openai_key)
    # TO-DO: Create value list from existing columns in DB
    value_list = ["kindness", "cooperation", "honesty"]  # hard-coded
    age = 12  # hard-coded
    # fetch transcript data based on each video id
    for video_id in video_ids:
        try:
            response = supabase.table('videos').select("transcript").eq("video_id", video_id).execute()
            data = response.data
            if data:
                transcript = data[0]['transcript']
                # value_list = data[0]['value_list']
                # age = data[0]['age']

        except APIError as e:
            print(f"API Error: {e.message}")
            return

    # TO-DO: change the below prompt to give an age range instead of just a number
        # what the prompt should include: Also recommend an appropriate age rating out of the following labels based on the following YouTube video transcript: preschool (age 4 and under), younger (age 5-8), and older (age 9-12)

    prompt = f"""
        
        On a scale from 1 to 10, rate how much the following YouTube video transcript promotes each of these values
        Also recommend an appropriate integer age based on the following YouTube video transcript

        Transcript:
        {transcript}

        Values:
        {value_list}

        Output:
        Respond in the following JSON format but without the 'json' prefix before the dictionary:
        {{
            "value_dict": {{
                "kindness": "insert score",
                "cooperation": "insert score",
                "honesty": "insert score"
            }},
            "age_rating": "age"
        }}
        Provide a dictionary that maps each value to its corresponding score.
        Provide the recommended age rating label.
    """

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"user", "content":prompt, "response_format":"tyoe"}
        ]
    )
    print(completion.choices[0].message.content)
    # TO-DO: iterate thru json output and insert value scores for each value and age rating into DB
    output_dict = json.loads(completion.choices[0].message.content)
    try:
        response = supabase.table('videos').update([
           {'age_rating': output_dict['age_rating']} 
        ]).eq('video_id', video_id).execute()
    except APIError as e:
        print(f"API Error: {e.message}")
        return
    
    try:
        for value, value_score in output_dict["value_dict"].items():
            print(value)
            print(value_score)
            response = supabase.table('videos').update([
            {value: value_score} 
            ]).eq('video_id', video_id).execute()
    except APIError as e:
        print(f"API Error: {e.message}")
        return
    print("success")
    
    # print(output_dict["age_rating"])
    # for value, value_score in output_dict["value_dict"].items():
    #     print(value)
    #     print(value_score)



def main():
    video_ids = ["STUDDsT6lYI"]  # this will be what we get from the scraper
    video_details = get_youtube_video_details(video_ids)
    insert_into_supabase(video_details)
    rate_videos(video_ids)

if __name__ == '__main__':
    main()
