__author__ = "Gang Fang"
__copyright__ = "Copyright 2018, The Ziroom Room Search Project"

import bs4 as bs
import urllib.request
import json
import re

base_url_threerooms = "http://www.ziroom.com/z/nl/z2-r2100TO3000-u3-a2.html"
base_url_tworooms = "http://www.ziroom.com/z/nl/z2-r2100TO3000-u2-a2.html"
rooms = []



def run():
  print('--- start scraping ---')
  num_pages_of_threerooms = get_num_pages(base_url_threerooms)
  loop_over_pages(base_url_threerooms, num_pages_of_threerooms)
  num_pages_of_tworooms = get_num_pages(base_url_tworooms)
  loop_over_pages(base_url_tworooms, num_pages_of_tworooms)

  print('--- start ranking ---')
  score_rooms(rooms)

  print('start sorting')
  sort_rooms(rooms)

  print('--- start making CSV ---')
  make_CSV(rooms)



def get_num_pages(base_url):
  try:
    soup = make_soup(base_url)
    pagenum_text = soup.find_all('span', {'class': 'pagenum'})[0].text # .text include child text, compared to .string
    num_pages = int(pagenum_text[pagenum_text.find('/') + 1:])
  except IndexError:
    num_pages = 1

  return num_pages



def make_soup(url):
  hdr = { 'User-Agent' : 'Mozilla/5.0 (Windows NT 6.1; Win64; x64)' } # fake User-Agent to get access to data
  req = urllib.request.Request(url, headers=hdr)
  sauce = urllib.request.urlopen(req).read()
  return bs.BeautifulSoup(sauce, 'html5lib')



def loop_over_pages(base_url, num_pages):
  # commute_time_ceiling = int(input('Max commute time: '))
  commute_time_ceiling = 40

  for current_page_idx in range(1, num_pages + 1):
    get_rooms_in_one_page(base_url, current_page_idx, commute_time_ceiling)
  


def get_rooms_in_one_page(base_url, current_page_idx, commute_time_ceiling):
  current_page_url = base_url + '?p=' + str(current_page_idx)
  current_soup = make_soup(current_page_url)

  rooms_in_one_page = current_soup.find_all('li', {'class': 'clearfix'})

  for room in rooms_in_one_page:
    print('--- a new room ---')
    if 'zry' in room['class']:  # avoid the promo item
      continue
    img_div = room.select('div.img.pr')[0]
    if 'defaultPZZ' in img_div.img['_src']:
      continue
    
    try:
      room_dict = make_room_dict(room)
      room_dict = modify_room_dict(room_dict)

      if commute_time_ceiling < int(room_dict['total_commute_time']):
        continue

      print(room_dict)
      rooms.append(room_dict)
    except Exception as exception:
      template = "An exception of type {0} occurred. Arguments:\n{1!r}"
      message = template.format(type(exception).__name__, exception.args)
      print(message)



def make_room_dict(room):
  distance_info = room.find_all('div', {'class': 'detail'})[0].find_all('p')[1].span.string
  start_idx = distance_info.find('线') + 1
  end_idx = distance_info.find('站')
  time_rm_to_station = int(distance_info[end_idx+1:-1]) / 1.4
  nearest_metro_station = distance_info[start_idx:end_idx] + '-地铁站'   # distance
  total_commute_time = round((metro_commute_time(nearest_metro_station, '人民大学') + time_rm_to_station) / 60.0)

  # should refactor the following: get rid of all unnecessary char in strings
  return {
    'total_commute_time': str(total_commute_time),
    'num_of_rooms': room.find_all('div', {'class': 'detail'})[0].find_all('span')[2].string,
    'unit_size': room.find_all('div', {'class': 'detail'})[0].span.string,
    'rent': room.find_all('p', {'class': 'price'})[0].text.strip(),
    'url_to_details': 'http://' + room.h3.a['href'][2:]
  }


def metro_commute_time(origin, destination):
  query_url = 'http://api.map.baidu.com/direction/v1?mode=transit&origin=' + urllib.parse.quote_plus(origin) + '&destination=' + urllib.parse.quote_plus(destination) + '&region=%E5%8C%97%E4%BA%AC&output=json&ak=bj3X5CsocqnilpXEVdWBexolszRPPXLH'
  res = urllib.request.urlopen(query_url).read()
  response_dict = json.loads(res.decode('utf-8'))
  return int(response_dict['result']['routes'][0]['scheme'][0]['duration'])



def modify_room_dict(room_dict):
  """
  add url to floorplan pic
  add name of room, which has room ID
  """
  details_page_soup = make_soup(room_dict['url_to_details'])
  room_dict['name'] = details_page_soup.select('div.room_name')[0].h2.string.strip()
  room_dict['floorplan_url'] = details_page_soup.select('div.lidiv')[-1].img['src']
  return room_dict



def score_rooms(rooms):
  """
  Compute boundary values for each factor
  Then compute and assign partial_score to each room

  partial_score considers factors of commute time, # rooms, unit size and rent
  factor adjacency should be added manually, other factors will be added after looking

  All factors scale from 0 to 1
  """
  def get_commute_time_int(room):
    return int(room['total_commute_time'])
  def get_unit_size_float(room):
    return float(room['unit_size'][:room['unit_size'].find(' ')])
  def get_rent_int(room):
    return int(re.findall('\d+', room['rent'])[0])
  def get_num_of_rooms_int(room):
    return int(room['num_of_rooms'][0])

  commute_time_list = list(map(get_commute_time_int, rooms))
  unit_size_list = list(map(get_unit_size_float, rooms))
  rent_list = list(map(get_rent_int, rooms))

  longest_commute_time = max(commute_time_list)
  shortest_commute_time = min(commute_time_list)
  largest_unit_size = max(unit_size_list)
  smallest_unit_size = min(unit_size_list)
  highest_rent = max(rent_list)
  lowest_rent = min(rent_list)


  for room in rooms:
    factor_commute_time = (longest_commute_time - get_commute_time_int(room)) / (longest_commute_time - shortest_commute_time)
    factor_num_rooms = (3 - get_num_of_rooms_int(room)) / (3 - 2)
    factor_unit_size = (get_unit_size_float(room) - smallest_unit_size) / (largest_unit_size - smallest_unit_size)
    factor_rent = (highest_rent - get_rent_int(room)) / (highest_rent - lowest_rent)
    # factor_adjacency = 1 for not adjacent, or 0 for adjacent

    partial_score_before_rounding = factor_commute_time + 0.3 * factor_num_rooms + 0.5 * factor_unit_size + 0.9 * factor_rent # + 0.9 factor_adjacency
    room['partial_score'] = str(round(partial_score_before_rounding, 4))



def sort_rooms(rooms):
  rooms.sort(key=lambda room: float(room['partial_score']), reverse=True)



def make_CSV(rooms):
  filename = 'rooms.csv'
  f = open(filename, 'w')

  # headers = 'name, commute_time, num_rooms, unit_size, rent, url_to_details\n'
  # f.write(headers)
  for room in rooms:
    f.write(room['name'] + ',' + room['total_commute_time'] + ',' + room['num_of_rooms'] + ',' + room['unit_size'] + ',' + room['rent'] + ',' + room['url_to_details'] + ',' + room['floorplan_url'] + ',' + room['partial_score'] + '\n')

  f.close()





run()




# Unit tests
# score_rooms([{'total_commute_time': '50', 'num_of_rooms': '3室1厅', 'unit_size': '10 ㎡', 'rent': '￥ 2800        (每月)', 'url_to_details': 'http://www.ziroom.com/z/vr/60895710.html', 'name': '\n                        鑫苑鑫都汇3居室-03卧\n                         ', 'floorplan_url': 'http://pic.ziroom.com/house_images/g2/M00/D1/E3/ChAFfVo7y6WAHZRVAAIzw19UObU226.jpg'}, {'total_commute_time': '70', 'num_of_rooms': '2室1厅', 'unit_size': '12 ㎡', 'rent': '￥ 2200        (每月)', 'url_to_details': 'http://www.ziroom.com/z/vr/60895710.html', 'name': '\n                        鑫苑鑫都汇3居室-03卧\n                         ', 'floorplan_url': 'http://pic.ziroom.com/house_images/g2/M00/D1/E3/ChAFfVo7y6WAHZRVAAIzw19UObU226.jpg'}, {'total_commute_time': '20', 'num_of_rooms': '3室1厅', 'unit_size': '11 ㎡', 'rent': '￥ 2500        (每月)', 'url_to_details': 'http://www.ziroom.com/z/vr/60895710.html', 'name': '\n                        鑫苑鑫都汇3居室-03卧\n                         ', 'floorplan_url': 'http://pic.ziroom.com/house_images/g2/M00/D1/E3/ChAFfVo7y6WAHZRVAAIzw19UObU226.jpg'}])