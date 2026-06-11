import urllib.request, json, urllib.parse, re, time, os
from datetime import datetime, timezone, timedelta

YT_KEY  = os.environ['YT_KEY']   # 크리에이터별 넥슨영상 search (무거운 작업)
YT_KEY2 = os.environ['YT_KEY2']  # 주간영상 search + 조회수 (가벼운 작업)
now     = datetime.now(timezone.utc)

# KST 기준 이번 주 월~일 범위
kst_now     = now + timedelta(hours=9)
kst_weekday = kst_now.weekday()
kst_monday  = (kst_now - timedelta(days=kst_weekday)).replace(
                hour=0, minute=0, second=0, microsecond=0)
kst_sunday  = kst_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
utc_monday  = kst_monday - timedelta(hours=9)
utc_sunday  = kst_sunday - timedelta(hours=9)
week_label  = f"{kst_monday.strftime('%Y.%m.%d')}~{kst_sunday.strftime('%Y.%m.%d')}"
print(f"실행: {now.strftime('%Y-%m-%d %H:%M')} UTC | 수집기간(KST): {week_label}")

EXCL_TITLE = ['tata nexon','nexon ev','nexon car','tractor','nexon suv',
              'rohit','pehchan','ram ram','indianvehicle','earn with',
              'indian bike','farming simulator']
EXCL_CH    = ['tata','rohit','pehchan','hr vehicle','harshgamer','akash',
              'earn with','pro ivs','kumar','orin-chan']

GAME_QUERIES = [
    ('넥슨',       'Nexon game -tata -car -ev -suv -tractor'),
    ('카잔',       'Khazan OR "First Berserker Khazan" OR "Berserker Khazan"'),
    ('메이플',     'MapleStory game'),
    ('블루아카이브', '"Blue Archive"'),
    ('ARC레이더스', '"Arc Raiders"'),
    ('엠바크',     '"Embark Studios"'),
    ('퍼디',       '"First Descendant"'),
    ('EOTU',      '"Embers of the Uncrowned"'),
    ('서든어택',   '"Sudden Attack" game'),
    ('빈디커스',   'Vindictus'),
    ('마비노기',   'Mabinogi game'),
    ('카트라이더', 'KartRider'),
    ('DNF',       '"Dungeon Fighter" OR "DNF Duel"'),
    ('낙원',       'Nakwon game OR "Nakwon: Last Paradise"'),
]

NEXON_KW = ['nexon','khazan','berserker','maplestory','blue archive','arc raiders',
            'embark','first descendant','embers of the uncrowned','sudden attack',
            'vindictus','mabinogi','kartrider','dungeon fighter','nakwon','dnf duel']
EXCL_VIDEO = ['tata nexon','nexon ev','nexon car','nexon suv']

def is_clean(title, channel):
    t, ch = title.lower(), channel.lower()
    if re.search(r'[\uAC00-\uD7AF\u0900-\u097F]', t+ch): return False
    if any(x in t  for x in EXCL_TITLE): return False
    if any(x in ch for x in EXCL_CH):    return False
    ch_latin = len(re.findall(r'[a-zA-Z]', ch))
    if len(ch.replace(' ','')) > 3 and ch_latin/max(len(ch.replace(' ','')),1) < 0.3:
        return False
    return True

def tag_game(title):
    t = title.lower()
    if 'khazan' in t or 'berserker' in t:              return '카잔'
    if 'arc raiders' in t:                              return 'ARC레이더스'
    if 'embark' in t:                                   return '엠바크'
    if 'first descendant' in t:                         return '퍼디'
    if 'blue archive' in t:                             return '블루아카이브'
    if 'maplestory' in t or 'maple story' in t:         return '메이플'
    if 'embers of the uncrowned' in t or 'eotu' in t:  return 'EOTU'
    if 'sudden attack' in t:                            return '서든어택'
    if 'vindictus' in t:                                return '빈디커스'
    if 'mabinogi' in t:                                 return '마비노기'
    if 'kartrider' in t:                                return '카트라이더'
    if 'dungeon fighter' in t or 'dnf duel' in t:       return 'DNF'
    if 'nakwon' in t:                                   return '낙원'
    return '넥슨'

def yt_get(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'  요청 실패: {e}'); return {}

with open('creators.json', encoding='utf-8') as f:
    creators = json.load(f)

# ═══════════════════════════════════════════════════════════
# [1] 주간영상 수집
# ═══════════════════════════════════════════════════════════
print('\n[주간영상] 수집 시작')
pub_after  = urllib.parse.quote(utc_monday.strftime('%Y-%m-%dT%H:%M:%SZ'))
pub_before = urllib.parse.quote(utc_sunday.strftime('%Y-%m-%dT%H:%M:%SZ'))

pool, seen, game_counts = [], set(), {}

for game_tag, kw in GAME_QUERIES:
    url = (f'https://www.googleapis.com/youtube/v3/search'
           f'?part=snippet&q={urllib.parse.quote(kw)}&type=video&order=date'
           f'&publishedAfter={pub_after}&publishedBefore={pub_before}'
           f'&maxResults=50&relevanceLanguage=en&key={YT_KEY2}')
    d = yt_get(url)
    if 'error' in d:
        print(f'  [{game_tag}] 에러: {d["error"]["message"]}')
        time.sleep(1); continue
    added = 0
    for item in d.get('items', []):
        vid   = item['id']['videoId']
        title = item['snippet']['title']
        ch    = item['snippet']['channelTitle']
        if vid in seen: continue
        if not is_clean(title, ch): continue
        if game_counts.get(game_tag, 0) >= 15: continue
        seen.add(vid)
        pool.append({'item': item, 'game': game_tag})
        game_counts[game_tag] = game_counts.get(game_tag, 0) + 1
        added += 1
    print(f'  [{game_tag}] {len(d.get("items",[]))}개 검색 → {added}개 통과')
    time.sleep(0.3)

# 조회수 배치 수집
all_ids = [p['item']['id']['videoId'] for p in pool]
v_stats = {}
for i in range(0, len(all_ids), 50):
    batch = ','.join(all_ids[i:i+50])
    d2 = yt_get(f'https://www.googleapis.com/youtube/v3/videos?part=statistics&id={batch}&key={YT_KEY2}')
    for item in d2.get('items', []):
        v_stats[item['id']] = int(item['statistics'].get('viewCount', 0))
    time.sleep(0.1)

weekly_videos = sorted([{
    'id':      p['item']['id']['videoId'],
    'title':   p['item']['snippet']['title'],
    'channel': p['item']['snippet']['channelTitle'],
    'thumb':   p['item']['snippet']['thumbnails'].get('medium',{}).get('url',''),
    'date':    p['item']['snippet']['publishedAt'],
    'views':   v_stats.get(p['item']['id']['videoId'], 0),
    'url':     f"https://www.youtube.com/watch?v={p['item']['id']['videoId']}",
    'game':    p['game'],
    'plat':    'YouTube',
} for p in pool], key=lambda x: x['views'], reverse=True)

# 기존 데이터와 같은 주면 머지, 다른 주면 교체
try:
    with open('weekly_videos.json', encoding='utf-8') as f:
        existing = json.load(f)
    if existing.get('week_label') == week_label:
        existing_ids = {v['id'] for v in existing.get('videos', [])}
        new_only = [v for v in weekly_videos if v['id'] not in existing_ids]
        weekly_videos = sorted(
            existing.get('videos', []) + new_only,
            key=lambda x: x['views'], reverse=True
        )
        print(f'  기존 머지: 신규 {len(new_only)}개 추가 → 총 {len(weekly_videos)}개')
    else:
        print(f'  새 주 시작: {len(weekly_videos)}개')
except:
    print(f'  신규 생성: {len(weekly_videos)}개')

# ═══════════════════════════════════════════════════════════
# [2] 크리에이터별 넥슨 영상 수집
# ═══════════════════════════════════════════════════════════
print('\n[크리에이터 영상] 수집 시작')

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

cid_map = {}
for c in creators:
    name = c.get('name','')
    if c.get('platform') != 'YouTube': continue
    cid = ch_stats.get(name,{}).get('channelId','') or id_map.get(name,'')
    if cid: cid_map[name] = cid

for name, handle in handle_map.items():
    if name not in cid_map:
        d = yt_get(f'https://www.googleapis.com/youtube/v3/channels'
                   f'?part=id&forHandle={urllib.parse.quote(handle)}&key={YT_KEY}')
        cid = d.get('items',[{}])[0].get('id','')
        if cid: cid_map[name] = cid
        time.sleep(0.1)

existing_videos = {}
try:
    with open('creator_videos.json', encoding='utf-8') as f:
        existing_videos = json.load(f).get('videos', {})
except: pass

nexon_q = urllib.parse.quote(
    'nexon OR khazan OR berserker OR maplestory OR "blue archive" OR "arc raiders" '
    'OR "embark studios" OR "first descendant" OR "embers of the uncrowned" '
    'OR "sudden attack" OR vindictus OR mabinogi OR kartrider '
    'OR "dungeon fighter" OR nakwon OR "dnf duel"'
)

creator_videos = {}
for c in creators:
    name = c.get('name','')
    if not name: continue

    if c.get('platform') != 'YouTube':
        creator_videos[name] = existing_videos.get(name, {'nexon':[]})
        continue

    cid = cid_map.get(name,'')
    if not cid:
        creator_videos[name] = existing_videos.get(name, {'nexon':[]})
        continue

    existing  = existing_videos.get(name, {'nexon':[]})
    ex_ids    = {v['id'] for v in existing.get('nexon',[])}
    has_data  = len(ex_ids) > 0

    since_str = ''
    if has_data:
        since_dt  = (now - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        since_str = f'&publishedAfter={urllib.parse.quote(since_dt)}'

    search_url = (f'https://www.googleapis.com/youtube/v3/search'
                  f'?part=snippet&channelId={cid}&q={nexon_q}'
                  f'&type=video&order=date{since_str}'
                  f'&maxResults={"10" if has_data else "50"}&key={YT_KEY}')
    d_nexon = yt_get(search_url)
    time.sleep(0.2)

    new_nexon = []
    for item in d_nexon.get('items', []):
        vid   = item['id'].get('videoId','')
        title = item['snippet'].get('title','')
        date  = item['snippet'].get('publishedAt','')
        tl    = title.lower()
        if (vid and vid not in ex_ids
                and any(k in tl for k in NEXON_KW)
                and not any(x in tl for x in EXCL_VIDEO)):
            new_nexon.append({
                'id':    vid,
                'title': title,
                'date':  date,
                'game':  tag_game(title),
                'url':   f'https://www.youtube.com/watch?v={vid}'
            })

    all_nexon = existing.get('nexon',[]) + new_nexon
    seen_cr   = set()
    deduped   = []
    for v in sorted(all_nexon, key=lambda x: x.get('date',''), reverse=True):
        if v['id'] not in seen_cr:
            seen_cr.add(v['id']); deduped.append(v)

    creator_videos[name] = {'nexon': deduped}
    if new_nexon:
        print(f'  {name}: 신규 {len(new_nexon)}개 (누적 {len(deduped)}개)')

yt_cnt = len([c for c in creators if c.get('platform')=='YouTube' and cid_map.get(c.get('name',''))])
print(f'  완료: YouTube {yt_cnt}명 처리')

# ═══════════════════════════════════════════════════════════
# 저장
# ═══════════════════════════════════════════════════════════
print('\n[저장]')
with open('weekly_videos.json','w',encoding='utf-8') as f:
    json.dump({
        'videos':     weekly_videos,
        'week_label': week_label,
        'week_start': utc_monday.isoformat(),
        'week_end':   utc_sunday.isoformat(),
        'fetched_at': now.isoformat(),
        'count':      len(weekly_videos)
    }, f, ensure_ascii=False, indent=2)

with open('creator_videos.json','w',encoding='utf-8') as f:
    json.dump({'videos': creator_videos, 'fetched_at': now.isoformat()},
              f, ensure_ascii=False, indent=2)

print('완료')
