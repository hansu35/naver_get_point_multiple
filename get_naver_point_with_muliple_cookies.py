import requests
import json
import os
from datetime import datetime

db_token = os.environ.get("CLOUD_DB_AUTH_TOKEN")
db_end_point = os.environ.get("CLOUD_DB_END_POINT")

naver_point_list_url =  "https://new-m.pay.naver.com/api/adreward/list?deviceType=ios&from=ad_list&channelId=pay&collectionId=benefit&category=all&groupId=6259172cb3752f94feb57e47&pageSize=100"
telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
telegram_channel_id = os.environ.get("TELEGRAM_CHAT_ID")
campaign_saved_file_name = 'visited_campaign_id.txt'

"""
사용자의 정보, 
id : 깃에서 쓸 아이디, 영어로만 적으면 문제 없을듯하다, 로그인 관련 문제가 있을때 아이디 기준으로 텔레그램을 보내고 하려고 한다. 
name: 로그인이 문제가 있을때 호명하기 위한 이름
cookie: 네이버 쿠키, 사실상 이거 만 있으면 된다. 
{
  "id":"id",
  "name": "hansu",
  "cookie":{}
}
"""

# os.system(f'echo \'list_count={new_count}\' > outputs')
# cat outputs >> $GITHUB_OUTPUT
# echo "{name}={value}" >> $GITHUB_ENV
def make_cookiejar_dict(cookies_str):
    # alt: `return dict(cookie.strip().split("=", maxsplit=1) for cookie in cookies_str.split(";"))`
    cookiejar_dict = {}
    for cookie_string in cookies_str.split(";"):
        # maxsplit=1 because cookie value may have "="
        cookie_key, cookie_value = cookie_string.strip().split("=", maxsplit=1)
        cookiejar_dict[cookie_key] = cookie_value
    return cookiejar_dict

# 사용자 한명의 네이버 로그인 세션 객체
class NaverUser(requests.Session):
  # 초기로 세션을 로드 해준다. 
  def __init__(self, dict_str):
    super().__init__()
    self. header = {
      "User-Agent" : "Mozilla/5.0 (iPod; CPU iPhone OS 14_5 like Mac OS X) AppleWebKit/605.1.15 \
      (KHTML, like Gecko) CriOS/87.0.4280.163 Mobile/15E148 Safari/604.1"
      }

    self.dict_str = dict_str
    self.data = json.loads(dict_str)
    self.id = self.data["id"]
    self.name = self.data["name"]
    self.point = 0
      
    self.available = True
    available = os.environ.get(self.id)
    if available != None and available == "N":
      self.available = False


    cookie = requests.utils.cookiejar_from_dict(make_cookiejar_dict(self.data["cookie"]))
    self.cookies.update(cookie)

  # 포인트를 얻어온다. 리턴값은 (성공/실패 , 포인트 잔여 값)
  def get_point(self):
    if self.available == False:
      return (False, 0)

    point_url = "https://new-m.pay.naver.com/api/pointsHistory/pointsamount"
    response = self.post(point_url)

    if response.status_code != 200:
      self.available = False
      return (False, 0)
    # print(response.text)
    data = json.loads(response.text)

    if (data["result"] != None and data["result"]["reward"] and data["result"]["reward"]["balanceAmount"] != None):
      return (True, data["result"]["reward"]["balanceAmount"])

    #로그인은 정상적으로 성공했는데 금액이 없는경우는 뭘까? 
    print("포인트 얻어오는데는 성공 하지만 금액이 없는경우는 뭘까? ")
    print(response.text)
    return (False, 0)



## 텔레그램 메세지 전달. 
def send_telegram(chat_id, massage, ):
  datas = {
  'chat_id':chat_id,
  'text':massage ,
  'disable_web_page_preview': True
  }
  print(f'텔레그램 발송 데이터 {datas}')
  telegram_url = f'https://api.telegram.org/bot{telegram_bot_token}/sendMessage'
  r = requests.post(telegram_url, data=json.dumps(datas), headers={'Content-Type':'application/json'})

  if(r.status_code != 200):
    print('텔레그램 발송 실패.')
    print(r.text)


# cloud DB 요청.
def dbQuery(queryData):
  # print(json.dumps(queryData))
  r = requests.post(db_end_point, data=json.dumps(queryData), headers={'Content-Type':'application/json', 'Authorization':db_token})
  if(r.status_code == 200):
    # print(r.text)
    return json.loads(r.text)
  else:
    print(f'디비 요청 에러 {r.status_code} / {r.text}')
    return None


## 방문기록용 로그 파일관리.
## 파일로 기록하는게 맞는건가? 싶긴한데... 말이죠...
def get_visited_campaign_list():
  try:
    listData = dbQuery({'query':'query naver_points_ids_logs { naver_points_ids_logs ( limit:1000 order_by: [{check_date:DESC}]) {campaign_id}}'})
    if(listData != None):
      visited_list = listData["data"]["naver_points_ids_logs"]
      return visited_list
  except Exception as e:    
    print('예외가 발생했습니다.', e)
  return []

def save_visited_campaign_list(visited_campaign_id_list):
  dump = '['+visited_campaign_id_list[0:-1]+']'
  dbQuery({'query':'mutation naver_points_ids_logs { insert_naver_points_ids_logs ( objects:'+dump+') {affected_rows returning {rowid}} }'})
  




if __name__ == "__main__":
  # 네이버 계정을 여러개 만들어 주자. 
  naver_account_list = []
  naver_account_list.append(NaverUser(os.environ.get("NAVER_USER_2")))
  naver_account_list.append(NaverUser(os.environ.get("NAVER_USER_1")))

  n = None

  today = datetime.today().strftime("%Y-%m-%d")

  # 최초로 로그인을 유지시켜 주기 위해서 모두 한번씩 네이버를 방문해준다. 
  for one_account in naver_account_list:
    if one_account.available:
      ( r, point ) = one_account.get_point()
      if r: 
        n = one_account
        one_account.point = point
        print(f'포인트 변화 확인 {one_account.name}의 기존 포인트 {one_account.point}')
      else: 
        send_telegram(telegram_channel_id, f'{one_account.name}님 네이버 로그인 확인 필요(최초 로그인유지 확인실패).')




  # 이제 점검을 시작한다. 
  # 방문 목록을 가져온다. 
  visited_list = get_visited_campaign_list()
  print("방문 리스트")
  print(visited_list)
  new_visited_list_str = ""

  new_count = 0
  # 새로운 포인트 목록이 있는지 검사한다. 
  try:
    response = n.get(naver_point_list_url)
    data = json.loads(response.text)
    
    # print(data["result"]["ads"])
    
    # 전체 캠페인을 전부 확인.
    for one_campaign in data["result"]["ads"]:
      # 클릭시 포인트를 주지 않는다면.. 혹은 url이 없다면 제외.
      if one_campaign["clickRewardAmount"] == None or one_campaign["clickRewardAmount"] < 1 or one_campaign["viewUrl"] == '':
        continue

      # 포인트를 주더라도 방문록록에 있다면 제외.
      campaign_id = one_campaign["campaignId"]
      if any(c.get('campaign_id',0) == campaign_id for c in visited_list):
        continue
      print(f' 이캠페인 아이디는 없어서 진행 {campaign_id}')
      # 아니라면 텔레그램으로 알림을 하나 보내고 방문.
      send_telegram(telegram_channel_id, f'네이버 포인트 \n{one_campaign["title"]} \n링크: {one_campaign["viewUrl"]} \n클릭보상금: {one_campaign["clickRewardAmount"]} \n종료시기: {one_campaign["clickRewardEndAt"]}')
      new_count = new_count + 1
      # visited_list.add(campaign_id)
      new_visited_list_str += '{campaign_id:'+str(campaign_id)+', check_date:"'+one_campaign["clickRewardEndAt"]+'"},'

      # 모든 네이버 어카운트에서 한번씩 방문한다. 
      for one_account in naver_account_list:
        if one_account.available:
          r = one_account.get(one_campaign["viewUrl"])
          if r.status_code != 200:
            send_telegram(telegram_channel_id, f'{one_account.name}님 네이버 로그인 확인 필요(방문이후 포인트 체크 실패).')
            one_account.available = False

    # 캠페인을 모두 방문했다. 종료.
    # 방문했던 모든 리스트 새롭게 저장한다. 
    if new_count > 0:
    	save_visited_campaign_list(new_visited_list_str)

    # 모든 네이버 어카운트에서 포인트 변화를 확인한다. 
    for one_account in naver_account_list:
      if one_account.available:
        (r, point) = one_account.get_point()
        if r:
          diff = point - one_account.point
          print(f'포인트 변화 확인 {one_account.name}의 기존 포인트 {one_account.point} / 재 검사 포인트 {point}')
          if diff > 0:
            send_telegram(telegram_channel_id, f'{one_account.name}님 포인트 획득: {diff}')
        

  except Exception as e: 
    print('네이버 포인트 리스트 불러오기 실패')
    print(e)
    # 예외가 발생하면 실패로 전달한다. 
    send_telegram(telegram_channel_id, '네이버 포인트 리스트 불러오기 실패')

  # os.system(f'echo \'list_count={new_count}\' >> $GITHUB_OUTPUT')
  os.system(f'echo \'list_count=0\' >> $GITHUB_OUTPUT')
