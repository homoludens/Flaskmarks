"""
Get details about youtube videos.


"""

import yt_dlp
import requests
import re


def download_subtitles(subtitles_url):
    """
    Download subtitles from url found with yt_dlp
    """
    if subtitles_url:
        response = requests.get(subtitles_url, stream=True)
        # remove timestamps
        subtitles = re.sub(r'<c>|<\/c>|<\d{2}\W\d{2}\W\d{2}\W\d{3}>|align:start position:0%|\d{2}\W\d{2}\W\d{2}\W\d{3}\s\W{3}\s\d{2}\W\d{2}\W\d{2}\W\d{3}','',response.text)

    
    return subtitles


def get_youtube_info(youtube_url):
    """
    Get info about youtube video.

    """

    ydl_opts = dict(
        write_auto_sub=True,
        sub_lang='en',
        skip_download=True,
        writesubtitles=True,
        # allsubtitles= True,
        writeautomaticsub=True,
        noplaylist=True,
        playlist_items='1',
        quiet=True
     )

    res_subtitles = ''

    ydl = yt_dlp.YoutubeDL(ydl_opts) 
    res = ydl.extract_info(youtube_url, download=False)
    # print(res)

    url_type = 'video'
    if not 'vcodec' in res:
        url_type = 'channel'
        print(url_type)
    else:
        try:
            res_subtitles = download_subtitles(res['requested_subtitles']['en']['url'])
            # print(res_subtitles)
        except Exception as e:
            print("no subtitles")
            print(e)
    
    output = {
        'duration': res['duration'],
        'categories':  res['categories'],
        'uploader':  res['uploader'],
        'description': res['description'],
        'tags': res['tags'],
        'subtitles': res_subtitles,
        'channel_name': res['uploader'],
        'youtube_type': url_type,
        'title': res['title']
    }


    return output



def check_url_video(url):
    """
    Check if url is supported by ytdlp.
    """
    ydl = yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True, 'playlist_items': 1})
    try:
        info = ydl.extract_info(url, download=False)
        if info['channel_id'] == '':
            return False
        return True
    except Exception:
        return False



