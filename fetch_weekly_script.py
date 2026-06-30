import urllib.request, json, urllib.parse, re, time, os
from datetime import datetime, timezone

YT_KEY = os.environ['YT_KEY2']  # 채널통계 — 가벼운 작업이므로 YT_KEY2 사용
TW_ID  = os.environ['TW_ID']
TW_SEC = os.environ['TW_SEC']
now    = datetime.now(timezone.utc)

def yt_get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'  요청 실패: {e}'); return {}

with open('creators.json', encoding='utf-8') as f:
    creators = json.load(f)

ch_stats = {}
try:
    with open('channel_stats.json', encoding='utf-8') as f:
        ch_stats = json.load(f).get('stats', {})
except: pass

id_map, handle_map = {}, {}
for c in creators:
    if c.get('platform') != 'YouTube' or not c.get('url'): continue
    u = c['url']
    m_id = re.search(r'/channel/(UC[\w-]+)', u)
    m_h  = re.search(r'youtube\.com/@([\w.-]+)', u)
    if m_id:  id_map[c['name']] = m_id.group(1)
    elif m_h: handle_map[c['name']] = m_h.group(1)

def parse_yt_stats(item, name):
    s     = item.get('statistics', {})
    subs  = int(s.get('subscriberCount', 0))
    views = int(s.get('viewCount', 0))
    vids  = int(s.get('videoCount', 1)) or 1
    thumb = item.get('snippet',{}).get('thumbnails',{}).get('default',{}).get('url','')
    existing_thumb = ch_stats.get(name,{}).get('thumbnail','')
    ch_stats[name] = {
        'subscribers': subs,
        'avgViews':    views // vids,
        'thumbnail':   thumb or existing_thumb,
        'channelId':   item.get('id','')
    }

print('[채널통계] /channel/UC 배치 조회')
items_list = list(id_map.items())
for i in range(0, len(items_list), 50):
    batch      = items_list[i:i+50]
    ids_str    = ','.join(cid for _, cid in batch)
    id_to_name = {cid: nm for nm, cid in batch}
    d = yt_get(f'https://www.googleapis.com/youtube/v3/channels'
               f'?part=statistics,snippet&id={ids_str}&key={YT_KEY}')
    for item in d.get('items',[]):
        nm = id_to_name.get(item['id'],'')
        if nm: parse_yt_stats(item, nm)
    time.sleep(0.3)

print('[채널통계] @핸들 조회')
for name, handle in handle_map.items():
    d = yt_get(f'https://www.googleapis.com/youtube/v3/channels'
               f'?part=statistics,snippet&forHandle={urllib.parse.quote(handle)}&key={YT_KEY}')
    if d.get('items'): parse_yt_stats(d['items'][0], name)
    time.sleep(0.1)

print('[채널통계] 기타 URL')
other = [c for c in creators
         if c.get('platform')=='YouTube' and c.get('name','') not in ch_stats and c.get('url','')]
for c in other:
    name, u = c.get('name',''), c.get('url','')
    found = False
    for pattern, param in [(r'youtube\.com/user/([\w-]+)','forUsername'),
                            (r'youtube\.com/c/([\w-]+)','forUsername')]:
        m = re.search(pattern, u)
        if m:
            d = yt_get(f'https://www.googleapis.com/youtube/v3/channels'
                       f'?part=statistics,snippet&{param}={urllib.parse.quote(m.group(1))}&key={YT_KEY}')
            if d.get('items'): parse_yt_stats(d['items'][0], name); found=True; time.sleep(0.1); break
    if not found:
        d = yt_get(f'https://www.googleapis.com/youtube/v3/search'
                   f'?part=snippet&q={urllib.parse.quote(name)}&type=channel&maxResults=1&key={YT_KEY}')
        items = d.get('items') or []
        cid = items[0].get('id',{}).get('channelId','') if items else ''
        if cid:
            d2 = yt_get(f'https://www.googleapis.com/youtube/v3/channels'
                        f'?part=statistics,snippet&id={cid}&key={YT_KEY}')
            if d2.get('items'): parse_yt_stats(d2['items'][0], name)
        time.sleep(0.15)

print('[채널통계] Twitch')
tw_token = ''
try:
    req = urllib.request.Request('https://id.twitch.tv/oauth2/token',
        data=f'client_id={TW_ID}&client_secret={TW_SEC}&grant_type=client_credentials'.encode(),
        headers={'Content-Type':'application/x-www-form-urlencoded'}, method='POST')
    with urllib.request.urlopen(req) as r:
        tw_token = json.loads(r.read()).get('access_token','')
except Exception as e:
    print(f'  Twitch 토큰 에러: {e}')

if tw_token:
    for c in creators:
        if c.get('platform') != 'Twitch' or not c.get('url'): continue
        m = re.search(r'twitch\.tv/([\w]+)', c['url'])
        if not m: continue
        login = m.group(1).lower()
        try:
            def tw(path):
                req = urllib.request.Request(f'https://api.twitch.tv/helix/{path}',
                    headers={'Client-Id':TW_ID,'Authorization':f'Bearer {tw_token}'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return json.loads(r.read())
            ud = tw(f'users?login={login}').get('data') or []
            uid = ud[0].get('id','') if ud else ''
            if not uid: continue
            followers = tw(f'channels/followers?broadcaster_id={uid}').get('total',0)
            vods      = tw(f'videos?user_id={uid}&type=archive&first=5').get('data',[])
            avg_v     = sum(int(v.get('view_count',0)) for v in vods)//len(vods) if vods else 0
            existing_thumb = ch_stats.get(c['name'],{}).get('thumbnail','')
            ud2 = tw(f'users?id={uid}').get('data') or []
            prof = (ud2[0].get('profile_image_url','') if ud2 else '') or existing_thumb
            ch_stats[c['name']] = {'subscribers':followers,'avgViews':avg_v,'thumbnail':prof,'channelId':''}
        except Exception as e:
            print(f'  Twitch {c["name"]}: {e}')
        time.sleep(0.1)

print(f'  완료: {len(ch_stats)}명')
with open('channel_stats.json','w',encoding='utf-8') as f:
    json.dump({'stats':ch_stats,'fetched_at':now.isoformat(),'count':len(ch_stats)},
              f, ensure_ascii=False, indent=2)
print('[저장] channel_stats.json 완료')
