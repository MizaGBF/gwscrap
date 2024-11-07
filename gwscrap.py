import asyncio
import aiohttp
from contextlib import asynccontextmanager
from typing import Generator, Optional, Any
from datetime import datetime, timedelta, timezone
import json
import re
import signal
import sqlite3
import csv
import os
import statistics
import traceback
import glob

class Scraper():
    GBFG = ["1744673", "645927", "977866", "745085", "1317803", "940560", "1049216", "841064", "1036007", "705648", "599992", "1807204", "472465", "1161924", "432330", "1837508", "1880420", "678459", "632242", "1141898", "1380234", "1601132", "1580990", "844716", "581111", "1010961"]
    GBFG_NICKs = {
        "1837508" : "Nier!",
        "432330" : "Little Girls",
        "472465" : "Haruna",
        "1141898" : "Quatrebois",
        "1036007" : "Cumshot Happiness",
        "599992" : "Fleet"
    }
    TASK_COUNT = 80
    def __init__(self) -> None:
        print("GW Ranking Scraper 3.2")
        self.client = None
        self.loop = None
        self.gw = None
        self.gw_dates = None
        self.temp_gw_mode = False
        self.temp_dat = None
        self.imports = False
        # preparing urls
        self.crew_url = ""
        self.player_url = ""
        # empty save data
        self.data = {'id':0, 'cookie':'', 'user_agent':''}
        self.modified = False
        self.version = None
        self.vregex = re.compile("\\/assets\\/(\d+)\\/")
        # load our data
        if not self.load():
            self.save() # failed? we make an empty file
            print("No 'config.json' file found.\nAn empty 'config.json' files has been created\nPlease fill it with your cookie, user agent and GBF profile id")
            os._exit(0)

    @asynccontextmanager
    async def init_client(self) -> Generator['aiohttp.ClientSession', None, None]:
        try:
            self.client = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
            yield self.client
        finally:
            await self.client.close()

    def pexc(self, exception : Exception) -> str:
        try:
            return "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        except:
            return exception

    def exit(self, *args) -> None: # called by ctrl+C
        print("")
        self.save()
        os._exit(0)

    def load(self) -> bool: # load cookie and stuff
        try:
            with open('config.json') as f:
                data = json.load(f)
                self.data = data
                if isinstance(self.data.get('cookie', None), str):
                    self.data['cookie'] = self.str2cookie(self.data['cookie'])
                    self.modified = True
                return True
        except Exception as e:
            print('load(): ' + self.pexc(e))
            return False

    def save(self) -> bool: # save
        if self.modified:
            try:
                with open('config.json', 'w') as outfile:
                    json.dump(self.data, outfile)
                self.modified = False
                print("'config.json' updated")
                return True
            except Exception as e:
                print('save(): ' + self.pexc(e))
                return False

    def writeFile(self, data : Any, name : str) -> bool: # write our scraped ranking
        try:
            with open(name, 'w') as outfile:
                json.dump(data, outfile)
            return True
        except Exception as e:
            print('writeFile(): ' + self.pexc(e))
            return False

    def toggle_temp_data(self) -> None:
        if self.temp_gw_mode:
            self.gw = None
            self.temp_gw_mode = False
            print("Temporary GW mode disabled")
        else:
            while True:
                try:
                    s = input("Input the GW ID (Leave blank to quit):")
                    if s == "": return
                    self.gw = int(s)
                    if self.gw < 1: raise Exception()
                    break
                except:
                    print("Invalid number")
            while True:
                try:
                    s = input("Input the day (prelim, d1, d2, d3, d4):")
                    if s not in ['prelim', 'd1', 'd2', 'd3', 'd4']: raise Exception()
                    self.temp_dat = s
                    break
                except:
                    print("Invalid day")
            self.temp_gw_mode = True
            print("Internal variables set to GW", self.gw, "for day", self.temp_dat)

    # gw stuff
    def gw_url(self) -> None:
        base_url = "https://game.granbluefantasy.jp/teamraid{}".format((str(self.gw)).zfill(3))
        self.crew_url = base_url + "/rest/ranking/totalguild/detail/{}/0?_={}&t={}&uid={}"
        self.player_url = base_url + "/rest_ranking_user/detail/{}/0?_={}&t={}&uid={}"
    
    def check_gw(self, no_ongoing_check : bool = False) -> Optional[int]:
        if self.temp_gw_mode: return 0
        while True:
            try:
                print("Checking GW state...")
                if self.gw_dates is None or self.gw is None: # load from file
                    self.gw_dates = self.gw_set(self.data.get('dates', None))
                    self.gw = self.data.get('gw', None)
                    if self.gw_dates is None or self.gw is None: # try again
                        raise Exception()
                self.gw_url()
                self.save()
                match self.gw_day(): # -2 = undefined, -1 = hasn't started, 0 = prelim, 1 = interlude, 2-5 = day, 10+ break period of day, 20 = FR day, 30 = ended
                    case -1:
                        print("State: GW hasn't started yet")
                        return None
                    case (0|10) as d:
                        print("State: Preliminaries" + ("(On going)" if d >= 10 else ""))
                        if d == 0:
                            if not no_ongoing_check and input("Currently on going, are you sure you wanna continue ('y' to continue):").lower() != 'y':
                                return None
                        return 0
                    case 1|11:
                        print("State: Interlude")
                        return 0
                    case (2|3|4|5|12|13|14|15) as d:
                        if d > 10:
                            print("State: Day ", d-11)
                            return d-11
                        else:
                            print("State: Day ", d-1, "(On going)")
                            if not no_ongoing_check and input("Currently on going, are you sure you wanna continue ('y' to continue):").lower() != 'y':
                                return None
                            return d-1
                    case 20:
                        print("State: Final rally")
                        return 4
                    case 30:
                        print("State: GW has ended, deleting from memory...")
                        self.gw = None
                        self.gw_dates = None
                        self.data.pop('gw')
                        self.data.pop('dates')
                        self.modified = True
                        self.save()
                        return None
                    case _:
                        print("Unsupported state, debugging is needed")
                        print("Exiting...")
                        os._exit(0)
            except Exception as e:
                if str(e) != "":
                    print(self.pexc(e))
                print("No GW set in memory")
                while True:
                    try:
                        s = input("Input the GW ID (Leave blank to quit):")
                        if s == "": return None
                        self.gw = int(s)
                        if self.gw < 68: raise Exception()
                        self.data['gw'] = self.gw
                        break
                    except:
                        print("Invalid number")
                d = [0, 0, 0]
                while True:
                    try:
                        d[0] = int(input("Input the day:"))
                        if d[0] < 1 or d[0] > 31: raise Exception()
                        break
                    except:
                        print("Invalid number")
                while True:
                    try:
                        d[1] = int(input("Input the month:"))
                        if d[1] < 1 or d[1] > 12: raise Exception()
                        break
                    except:
                        print("Invalid number")
                while True:
                    try:
                        d[2] = int(input("Input the year:"))
                        if d[2] < 2023: raise Exception()
                        break
                    except:
                        print("Invalid number")
                self.gw_dates = self.gw_set(d)
                self.data['dates'] = d
                print("GW{} set to {}/{}/{}".format(self.data['gw'], self.data['dates'][0], self.data['dates'][1], self.data['dates'][2]))
                if input("Confirm ('y' to confirm)?").lower() == 'y':
                    self.modified = True
                else:
                    self.gw = None
                    self.gw_dates = None
                    self.data.pop('gw')
                    self.data.pop('dates')
                    print("Settings not saved")

    def gw_to_file(self, d : int) -> Optional[str]:
        try:
            if self.temp_gw_mode: return self.temp_dat
            return ['prelim', 'd1', 'd2', 'd3', 'd4'][d]
        except:
            return None

    def gw_set(self, DDMMYY : Optional[list]) -> Optional[dict]:
        if DDMMYY is None: return None
        dates = {}
        dates["Preliminaries"] = datetime.now(timezone.utc).replace(tzinfo=None).replace(year=DDMMYY[2], month=DDMMYY[1], day=DDMMYY[0], hour=19, minute=0, second=0, microsecond=0)
        dates["Interlude"] = dates["Preliminaries"] + timedelta(days=1, seconds=43200) # +36h
        dates["Day 1"] = dates["Interlude"] + timedelta(days=1) # +24h
        dates["Day 2"] = dates["Day 1"] + timedelta(days=1) # +24h
        dates["Day 3"] = dates["Day 2"] + timedelta(days=1) # +24h
        dates["Day 4"] = dates["Day 3"] + timedelta(days=1) # +24h
        dates["Day 5"] = dates["Day 4"] + timedelta(days=1) # +24h
        dates["End"] = dates["Day 5"] + timedelta(seconds=61200) # +17h
        return dates

    def gw_day(self): # -2 = undefined, -1 = hasn't started, 0 = prelim, 1 = interlude, 2-5 = day, 10+ break period of day, 20 = FR day, 30 = ended
        current_time = self.JST()
        if current_time < self.gw_dates["Preliminaries"]:
            return -1
        elif current_time >= self.gw_dates["End"]:
            return 30
        elif current_time >= self.gw_dates["Day 5"]:
            return 20
        elif current_time >= self.gw_dates["Day 1"]:
            it = ['Day 5', 'Day 4', 'Day 3', 'Day 2', 'Day 1']
            for i in range(1, len(it)): # loop to not copy paste this 5 more times
                if current_time >= self.gw_dates[it[i]]:
                    d = self.gw_dates[it[i-1]] - current_time
                    if d < timedelta(seconds=25200): return 16 - i
                    else: return 6 - i
        elif current_time > self.gw_dates["Interlude"]:
            return 1
        elif current_time > self.gw_dates["Preliminaries"]:
            d = self.gw_dates['Interlude'] - current_time
            if d < timedelta(seconds=25200): return 10
            else: return 0
        else:
            return -2

    def JST(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=32400) - timedelta(seconds=30)

    # utility used by build_crew_list
    def avg_of(self, l : list) -> str: 
        if len(l) == 0:
            return ''
        else:
            return str(sum(l)//len(l))

    def med_of(self, l : list) -> str:
        if len(l) == 0:
            return ''
        else:
            return str(statistics.median(l))

    def sum_of(self, l : list) -> str:
        if len(l) == 0:
            return 'n/a'
        else:
            return str(sum(l))

    async def getGameversion(self) -> Optional[int]: # get the game version
        try:
            response = await self.client.get('https://game.granbluefantasy.jp/', headers={'Host': 'game.granbluefantasy.jp', 'User-Agent': self.data['user_agent'], 'Accept-Encoding': 'gzip, deflate', 'Accept-Language': 'en', 'Connection': 'keep-alive'})
            async with response:
                if response.status != 200: raise Exception()
                res = self.vregex.findall((await response.read()).decode('utf-8'))
                return int(res[0]) # to check if digit
        except Exception as e:
            print(e)
            return None

    def updateCookie(self, header : dict) -> None: # update the cookie string
        B = self.str2cookie(header)
        for k, v in B.items():
            if k in self.data['cookie']:
                self.data['cookie'][k] = v
        self.modified = True

    def str2cookie(self, header : str) -> dict:
        cd = {}
        for c in header.split(";"):
            ct = c.split("=")
            cd[ct[0].strip()] = ct[1].strip()
        return cd

    async def requestRanking(self, page, crew = True) -> Optional[dict]: # request a ranking page and return the data
        try:
            ts = int(datetime.now(timezone.utc).replace(tzinfo=None).timestamp() * 1000)
            if crew: url = self.crew_url.format(page, ts, ts+300, self.data['id'])
            else: url = self.player_url.format(page, ts, ts+300, self.data['id'])
            self.client.cookie_jar.clear()
            self.client.cookie_jar.update_cookies(self.data['cookie'])
            response = await self.client.get(url, headers={'Cookie': self.data['cookie'], 'Referer': 'https://game.granbluefantasy.jp/', 'Origin': 'https://game.granbluefantasy.jp', 'Host': 'game.granbluefantasy.jp', 'User-Agent': self.data['user_agent'], 'X-Requested-With': 'XMLHttpRequest', 'X-VERSION': self.version, 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Accept-Encoding': 'gzip, deflate', 'Accept-Language': 'en', 'Connection': 'keep-alive', 'Content-Type': 'application/json'})
            async with response:
                if response.status != 200: raise Exception()
                try: self.updateCookie(response.headers['set-cookie'])
                except: pass
                return await response.json()
        except:
            return None

    async def crewProcess(self, q : asyncio.Queue, results : list) -> bool: # task for crew ranking
        while not q.empty():
            try:
                await asyncio.sleep(0)
                page = q.get_nowait()
            except:
                continue
            data = None
            while data is None or data['count'] == False:
                data = await self.requestRanking(page, True)
                if data is None or data['count'] == False: print("Crew: Error on page", page)
            for i in range(0, len(data['list'])):
                results[int(data['list'][i]['ranking'])-1] = data['list'][i]
            q.task_done()
        return True

    async def playerProcess(self, q : asyncio.Queue, results : list) -> bool: # task for player ranking
        while not q.empty():
            try:
                await asyncio.sleep(0)
                page = q.get_nowait()
            except:
                continue
            data = None
            while data is None or data['count'] == False:
                data = await self.requestRanking(page, False)
                if data is None or data['count'] == False: print("Player: Error on page", page)
            for i in range(0, len(data['list'])):
                results[int(data['list'][i]['rank'])-1] = data['list'][i]
            q.task_done()
        return True

    async def run(self, mode : int = 0) -> bool: # main loop. 0 = both crews and players, 1 = crews, 2 = players
        day = self.gw_to_file(self.check_gw())
        if day is None or self.temp_gw_mode:
            print("Invalid GW state to continue")
            return False
        # user check
        print("Make sure you won't overwrite a file with the suffix '{}' ".format(day))
        while True:
            s = input("Input a number of minutes to wait before starting, or leave blank to continue:")
            if s == "":
                break
            else:
                try:
                    s = int(s)
                    if s == 0:
                        break
                    elif s < 0:
                        print("Negative wait values aren't supported")
                    elif s > 240:
                        print("Big wait value detected")
                        if input("Input 'y' to confirm that it's not a typo, or anything else to modify:").lower() == 'y':
                            print("Waiting", s, "minutes")
                            await asyncio.sleep(s*60)
                            break
                    else:
                        print("Waiting", s, "minutes")
                        await asyncio.sleep(s*60)
                        break
                except:
                    print("Invalid wait value")
        # check the game version
        self.version = str(await self.getGameversion())
        if self.version is None:
            print("Impossible to get the game version currently")
            return False
        print("Current game version is", self.version)

        if mode == 0 or mode == 1:
            # crew ranking
            data = await self.requestRanking(1, True) # get the first page
            if data is None or data['count'] == False:
                print("Can't access the crew ranking")
                self.save()
                return False
            count = int(data['count']) # number of crews
            last = data['last'] # number of pages
            print("Crew ranking has {} crews and {} pages".format(count, last))
            results = [{} for x in range(count)] # make a big array
            for i in range(0, len(data['list'])): # fill the first slots with the first page data
                results[i] = data['list'][i]

            q = asyncio.Queue()
            for i in range(2, last+1): # queue the pages to retrieve
                await q.put(i)

            print("Scraping...")
            tasks = []
            for i in range(self.TASK_COUNT):
                tasks.append(self.crewProcess(q, results))
            await asyncio.gather(*tasks)

            self.writeFile(results, 'GW{}_crew_{}.json'.format(self.gw, day)) # save the result
            print("Done, saved to 'GW{}_crew_{}.json'".format(self.gw, day))
            self.save()

        if mode == 0 or mode == 2:
            # player ranking. exact same thing, I lazily copypasted.
            data = await self.requestRanking(1, False)
            if data is None or data['count'] == False:
                print("Can't access the player ranking")
                self.save()
                return False
            count = int(data['count'])
            last = data['last']
            print("Crew ranking has {} players and {} pages".format(count, last))
            results = [{} for x in range(count)]
            for i in range(0, len(data['list'])):
                results[i] = data['list'][i]

            q = asyncio.Queue()
            for i in range(2, last+1):
                await q.put(i)

            print("Scraping...")
            tasks = []
            for i in range(self.TASK_COUNT):
                tasks.append(self.playerProcess(q, results))
            await asyncio.gather(*tasks)

            self.writeFile(results, 'GW{}_player_{}.json'.format(self.gw, day))
            print("Done, saved to 'GW{}_player_{}.json'".format(self.gw, day))
            self.save()
        return True

    def buildGW(self, mode : int = 0) -> None: # build a .json compiling all the data withing json named with the 'days' suffix
        if self.check_gw() is None:
            print("Invalid GW state to continue")
            return
        days = ['prelim', 'd1', 'd2', 'd3', 'd4']
        if mode == 0 or mode == 1:
            results = {}
            print("Compiling crew data for GW{}...".format(self.gw)) # crew first
            for d in days:
                try:
                    with open('GW{}_crew_{}.json'.format(self.gw, d)) as f:
                        data = json.load(f)
                    for c in data:
                        if 'id' not in c: continue
                        if c['id'] not in results: results[c['id']] = {}
                        results[c['id']][d] = c['point']
                        results[c['id']]['name'] = c['name']
                        # we calculate the daily deltas here
                        if d == 'd1' and 'prelim' in results[c['id']]: results[c['id']]['delta_d1'] = str(int(results[c['id']][d]) - int(results[c['id']]['prelim']))
                        elif d == 'd2' and 'd1' in results[c['id']]: results[c['id']]['delta_d2'] = str(int(results[c['id']][d]) - int(results[c['id']]['d1']))
                        elif d == 'd3' and 'd2' in results[c['id']]: results[c['id']]['delta_d3'] = str(int(results[c['id']][d]) - int(results[c['id']]['d2']))
                        elif d == 'd4' and 'd3' in results[c['id']]: results[c['id']]['delta_d4'] = str(int(results[c['id']][d]) - int(results[c['id']]['d3']))
                        if d == days[-1]: results[c['id']]['ranking'] = c['ranking']
                except Exception as e:
                    print(self.pexc(e))
            self.writeFile(results, 'GW{}_crew_full.json'.format(self.gw))
            print("Done, saved to 'GW{}_crew_full.json'".format(self.gw))

        if mode == 0 or mode == 2:
            results = {}
            print("Compiling player data for GW{}...".format(self.gw)) # player next, exact same thing
            for d in days:
                try:
                    with open('GW{}_player_{}.json'.format(self.gw, d)) as f:
                        data = json.load(f)
                    for c in data:
                        if c['user_id'] not in results: results[c['user_id']] = {}
                        results[c['user_id']][d] = c['point']
                        results[c['user_id']]['name'] = c['name']
                        results[c['user_id']]['level'] = c['level']
                        if d == 'd1' and 'prelim' in results[c['user_id']]: results[c['user_id']]['delta_d1'] = str(int(results[c['user_id']][d]) - int(results[c['user_id']]['prelim']))
                        elif d == 'd2' and 'd1' in results[c['user_id']]: results[c['user_id']]['delta_d2'] = str(int(results[c['user_id']][d]) - int(results[c['user_id']]['d1']))
                        elif d == 'd3' and 'd2' in results[c['user_id']]: results[c['user_id']]['delta_d3'] = str(int(results[c['user_id']][d]) - int(results[c['user_id']]['d2']))
                        elif d == 'd4' and 'd3' in results[c['user_id']]: results[c['user_id']]['delta_d4'] = str(int(results[c['user_id']][d]) - int(results[c['user_id']]['d3']))
                        if d == days[-1]:
                            results[c['user_id']]['defeat'] = c['defeat']
                            results[c['user_id']]['rank'] = c['rank']
                except Exception as e:
                    print(self.pexc(e))
            self.writeFile(results, 'GW{}_player_full.json'.format(self.gw))
            print("Done, saved to 'GW{}_player_full.json'".format(self.gw))

    def makedb(self) -> None: # make a SQL file (useful for searching the whole thing)
        try:
            print("Building Database...")
            try:
                with open('GW{}_player_full.json'.format(self.gw)) as f:
                    pdata = json.load(f)
                with open('GW{}_crew_full.json'.format(self.gw)) as f:
                    cdata = json.load(f)
            except Exception as ex:
                print("Error:", self.pexc(ex))
                return
            conn = sqlite3.connect('GW{}.sql'.format(self.gw))
            c = conn.cursor()
            c.execute('CREATE TABLE players (rank int, user_id int, name text, level int, defeat int, preliminaries int, interlude_and_day1 int, total_1 int, day_2 int, total_2 int, day_3 int, total_3 int, day_4 int, total_4 int)')
            for id in pdata:
                c.execute("INSERT INTO players VALUES ({},{},'{}',{},{},{},{},{},{},{},{},{},{},{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id]['level'], pdata[id].get('defeat', 'NULL'), pdata[id].get('prelim', 'NULL'), pdata[id].get('delta_d1', 'NULL'), pdata[id].get('d1', 'NULL'), pdata[id].get('delta_d2', 'NULL'), pdata[id].get('d2', 'NULL'), pdata[id].get('delta_d3', 'NULL'), pdata[id].get('d3', 'NULL'), pdata[id].get('delta_d4', 'NULL'), pdata[id].get('d4', 'NULL')))
            c.execute('CREATE TABLE crews (ranking int, id int, name text, preliminaries int, day1 int, total_1 int, day_2 int, total_2 int, day_3 int, total_3 int, day_4 int, total_4 int)')
            for id in cdata:
                c.execute("INSERT INTO crews VALUES ({},{},'{}',{},{},{},{},{},{},{},{},{})".format(cdata[id].get('ranking', 'NULL'), id, cdata[id]['name'].replace("'", "''"), cdata[id].get('prelim', 'NULL'), cdata[id].get('delta_d1', 'NULL'), cdata[id].get('d1', 'NULL'), cdata[id].get('delta_d2', 'NULL'), cdata[id].get('d2', 'NULL'), cdata[id].get('delta_d3', 'NULL'), cdata[id].get('d3', 'NULL'), cdata[id].get('delta_d4', 'NULL'), cdata[id].get('d4', 'NULL')))
            conn.commit()
            conn.close()
            print('Done')
            return True
        except Exception as e:
            print('makedb(): ' + self.pexc(e))
            return False

    def build_crew_list(self, you_mode : bool = False) -> None: # build the gbfg leechlists on a .csv format
        temp = self.gw_to_file(self.check_gw())
        if temp is None:
            print("Invalid GW state to continue")
            return
        elif temp == "d4" or you_mode == True:
            temp = None # no temp mode for last day or you_mode
        remove_punctuation_map = dict((ord(char), None) for char in '\/*?:"<>|')
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_player_full.json'.format(self.gw)) as f:
                players = json.load(f)
        except Exception as e:
            print("Error:", self.pexc(e))
            return
        # one crew by one
        for c in gbfg:
            if you_mode and c not in ["581111"]: continue
            if 'private' in gbfg[c]: continue # ignore private crews
            name = self.GBFG_NICKs.get(c, gbfg[c]['name']).translate(remove_punctuation_map)
            if you_mode: filename = "GW{}_(You)_not_sorted.csv".format(self.gw)
            else: filename = "GW{}_{}.csv".format(self.gw, name)
            with open(filename, 'w', newline='', encoding="utf-8") as csvfile:
                llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
                llwriter.writerow(["", "#", "id", "name", "rank", "battle", "preliminaries", "interlude & day 1", "total 1", "day 2", "total 2", "day 3", "total 3", "day 4", "total 4"])
                l = []
                for p in gbfg[c]['player']:
                    if str(p['id']) in players:
                        if p['is_leader']: players[str(p['id'])]['name'] += " (c)"
                        l.append(players[str(p['id'])])
                        l[-1]['id'] = str(p['id'])
                    else:
                        l.append(p)
                crew_size = len(l)
                values = [[], [], [], [], [], [], [], [], [], [], []]
                for i in range(0, crew_size):
                    if not you_mode:
                        if temp is None:
                            mini = 999999999
                            idx = -1
                            for li in range(0, len(l)):
                                if 'rank' in l[li] and int(l[li]['rank']) <= mini:
                                    mini = int(l[li]['rank'])
                                    idx = li
                        else:
                            mini = -1
                            idx = -1
                            for li in range(0, len(l)):
                                if temp in l[li] and int(l[li][temp]) >= mini:
                                    mini = int(l[li][temp])
                                    idx = li
                    else:
                        idx = 0
                    if idx != -1:
                        pname = l[idx]['name'].replace('"', '\\"')
                        llwriter.writerow([str(i+1), l[idx].get('rank', 'n/a'), l[idx]['id'], pname, l[idx]['level'], l[idx].get('defeat', 'n/a'), l[idx].get('prelim', 'n/a'), l[idx].get('delta_d1', 'n/a'), l[idx].get('d1', 'n/a'), l[idx].get('delta_d2', 'n/a'), l[idx].get('d2', 'n/a'), l[idx].get('delta_d3', 'n/a'), l[idx].get('d3', 'n/a'), l[idx].get('delta_d4', 'n/a'), l[idx].get('d4', 'n/a')])
                        values[0].append(int(l[idx]['level']))
                        if 'defeat' in l[idx]: values[1].append(int(l[idx]['defeat']))
                        if 'prelim' in l[idx]: values[2].append(int(l[idx]['prelim']))
                        if 'delta_d1' in l[idx]: values[3].append(int(l[idx]['delta_d1']))
                        if 'd1' in l[idx]: values[4].append(int(l[idx]['d1']))
                        if 'delta_d2' in l[idx]: values[5].append(int(l[idx]['delta_d2']))
                        if 'd2' in l[idx]: values[6].append(int(l[idx]['d2']))
                        if 'delta_d3' in l[idx]: values[7].append(int(l[idx]['delta_d3']))
                        if 'd3' in l[idx]: values[8].append(int(l[idx]['d3']))
                        if 'delta_d4' in l[idx]: values[9].append(int(l[idx]['delta_d4']))
                        if 'd4' in l[idx]: values[10].append(int(l[idx]['d4']))
                        l.pop(idx)
                    else:
                        pname = l[0]['name'].replace('"', '\\"')
                        for p in gbfg[c]['player']:
                            if l[0]['id'] == p['id']:
                                if p['is_leader']: pname += " (c)"
                                break
                        llwriter.writerow([str(i+1), 'n/a', l[0]['id'], pname, l[0]['level'], 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a'])
                        values[0].append(int(l[0]['level']))
                        l.pop(0)
                llwriter.writerow(['', '', '', 'average', self.avg_of(values[0]), self.avg_of(values[1]), self.avg_of(values[2]), self.avg_of(values[3]), self.avg_of(values[4]), self.avg_of(values[5]), self.avg_of(values[6]), self.avg_of(values[7]), self.avg_of(values[8]), self.avg_of(values[9]), self.avg_of(values[10])])
                llwriter.writerow(['', '', '', 'median', self.med_of(values[0]), self.med_of(values[1]), self.med_of(values[2]), self.med_of(values[3]), self.med_of(values[4]), self.med_of(values[5]), self.med_of(values[6]), self.med_of(values[7]), self.med_of(values[8]), self.med_of(values[9]), self.med_of(values[10])])
                llwriter.writerow(['', '', '', 'total', '', self.sum_of(values[1]), self.sum_of(values[2]), self.sum_of(values[3]), self.sum_of(values[4]), self.sum_of(values[5]), self.sum_of(values[6]), self.sum_of(values[7]), self.sum_of(values[8]), self.sum_of(values[9]), self.sum_of(values[10])])
                llwriter.writerow(['', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
                gname = gbfg[c]['name'].replace('"', '\\"')
                llwriter.writerow(['', 'guild', str(c), gname, '', '', '', '', '', '', '', '', '', '', ''])
                print("{}: Done".format(filename))

    def build_temp_crew_ranking_list(self) -> None: # same thing but while gw is on going (work a bit differently, might be useful for scouting enemies)
        try:
            with open('GW{}_crew_full.json'.format(self.gw)) as f:
                crews = json.load(f)
        except Exception as e:
            print("Error:", self.pexc(e))
            return
        with open("GW{}_Crews.csv".format(self.gw), 'w', newline='', encoding="utf-8") as csvfile:
            llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
            llwriter.writerow(["", "#", "id", "name", "preliminaries", "day 1", "day 2", "day 3", "day 4", "total"])
            ranked = []
            unranked = []
            for c in self.GBFG:
                if c in crews:
                    gname = crews[c]['name'].replace('"', '\\"')
                    row = [crews[c].get('ranking', 'n/a'), c, gname]
                    row.append(crews[c].get('prelim', 'n/a'))
                    row.append(crews[c].get('delta_d1', 'n/a'))
                    row.append(crews[c].get('delta_d2', 'n/a'))
                    row.append(crews[c].get('delta_d3', 'n/a'))
                    row.append(crews[c].get('delta_d4', 'n/a'))
                    total = max(int(crews[c].get('d4', '0')), int(crews[c].get('prelim', '0'))+int(crews[c].get('delta_d1', '0'))+int(crews[c].get('delta_d2', '0'))+int(crews[c].get('delta_d3', '0'))+int(crews[c].get('delta_d4', '0')))
                    if total == 0: row.append('n/a')
                    else: row.append(total)
                else: continue
                if row[-1] == 'n/a': unranked.append(row)
                elif len(ranked) == 0: ranked.append(row)
                else:
                    for i in range(0, len(ranked)):
                        if int(row[-1]) > int(ranked[i][-1]):
                            ranked.insert(i, row)
                            break
                        elif i == len(ranked) -1:
                            ranked.append(row)
            ranked.extend(unranked)
            for i in range(0, len(ranked)):
                row = [i+1]
                row.extend(ranked[i])
                llwriter.writerow(row)
            print("GW{}_Crews.csv: Done".format(self.gw))

    def build_crew_ranking_list(self) -> None: # build the ranking of all the gbfg crews
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_crew_full.json'.format(self.gw)) as f:
                crews = json.load(f)
        except Exception as e:
            print("Error:", self.pexc(e))
            return
        with open("GW{}_Crews.csv".format(self.gw), 'w', newline='', encoding="utf-8") as csvfile:
            llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
            llwriter.writerow(["", "#", "id", "name", "players", "preliminaries", "day 1", "day 2", "day 3", "day 4", "final"])
            ranked = []
            unranked = []
            for c in gbfg:
                gname = gbfg[c]['name'].replace('"', '\\"')
                gcount = 'n/a' if 'player' not in gbfg[c] else len(gbfg[c]['player'])
                row = ['', c, gname, gcount]
                if c in crews:
                    row[0] = crews[c].get('ranking', 'n/a')
                    row.append(crews[c].get('prelim', 'n/a'))
                    row.append(crews[c].get('delta_d1', 'n/a'))
                    row.append(crews[c].get('delta_d2', 'n/a'))
                    row.append(crews[c].get('delta_d3', 'n/a'))
                    row.append(crews[c].get('delta_d4', 'n/a'))
                    row.append(crews[c].get('d4', 'n/a'))
                else: row = ['n/a', c, gname, gcount, 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a']
                if row[0] == 'n/a': unranked.append(row)
                elif len(ranked) == 0: ranked.append(row)
                else:
                    for i in range(0, len(ranked)):
                        if int(row[0]) < int(ranked[i][0]):
                            ranked.insert(i, row)
                            break
                        elif i == len(ranked) -1:
                            ranked.append(row)
            ranked.extend(unranked)
            for i in range(0, len(ranked)):
                row = [i+1]
                row.extend(ranked[i])
                llwriter.writerow(row)
            print("GW{}_Crews.csv: Done".format(self.gw))

    def build_player_list(self, captain_mode : bool = False) -> None:  # build the ranking of all the gbfg players
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_player_full.json'.format(self.gw)) as f:
                players = json.load(f)
        except Exception as e:
            print("Error:", self.pexc(e))
            return
        l = []
        na = []
        for c in gbfg:
            if 'private' in gbfg[c]: continue
            for p in gbfg[c]['player']:
                if captain_mode and not p['is_leader']: continue
                if str(p['id']) in players and 'rank' in players[str(p['id'])]:
                    x = 0
                    for x in range(0, len(l)):
                        if 'rank' in l[x] and int(players[str(p['id'])]['rank']) < int(l[x]['rank']):
                            l.insert(x, players[str(p['id'])])
                            l[x]['id'] = str(p['id'])
                            l[x]['guild'] = gbfg[c]['name']
                            l[x]['leader'] = p['is_leader']
                            break
                        elif x == len(l) - 1:
                            l.append(players[str(p['id'])])
                            l[-1]['id'] = str(p['id'])
                            l[-1]['guild'] = gbfg[c]['name']
                            l[-1]['leader'] = p['is_leader']
                            break
                    if len(l) == 0:
                        l.append(players[str(p['id'])])
                        l[-1]['id'] = str(p['id'])
                        l[-1]['guild'] = gbfg[c]['name']
                        l[-1]['leader'] = p['is_leader']
                else:
                    na.append({"id": str(p['id']), "name": p['name'], "level": p['level'], "guild": gbfg[c]['name'], 'leader': p['is_leader']})
        l += na
        if len(l) > 0:
            fname = ("GW{}_Captains.csv" if captain_mode else "GW{}_Players.csv").format(self.gw)
            with open(fname, 'w', newline='', encoding="utf-8") as csvfile:
                llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
                llwriter.writerow(["", "#", "id", "name", "guild", "rank", "battle", "preliminaries", "interlude & day 1", "day 2", "day 3", "day 4", "final"])
                for i in range(0, len(l)):
                    pname = l[i]['name'].replace('"', '\\"')
                    if not captain_mode: pname += (" (c)" if l[i]['leader'] else "")
                    gname = l[i]['guild'].replace('"', '\\"')
                    llwriter.writerow([str(i+1), l[i].get('rank', 'n/a'), l[i]['id'], pname, gname, l[i]['level'], l[i].get('defeat', 'n/a'), l[i].get('prelim', 'n/a'), l[i].get('delta_d1', 'n/a'), l[i].get('delta_d2', 'n/a'), l[i].get('delta_d3', 'n/a'), l[i].get('delta_d4', 'n/a'), l[i].get('d4', 'n/a')])
            print("{}: Done".format(fname))
        else:
            print("Error, not sufficient or complete player data")

    def buildGbfgFile(self) -> None: # check the gbfg folder for any json files and fuse the data into one
        # gbfg.json is used in other functions, it contains the crew member lists
        try:
            files = glob.glob("gbfg/*.json")
            final = {}
            for fn in files:
                with open('{}'.format(fn)) as f:
                    content = json.load(f)
                    for id in content:
                        if 'private' in content[id] and id in final:
                            continue
                        else:
                            final[id] = content[id]
            with open('gbfg.json', 'w') as f:
                json.dump(final, f)
            print("Success: 'gbfg.json' created")
            public = len(final)
            for c in final:
                if 'private' in final[c]: public -= 1
            print(public, "/", len(final), "public crew(s)")
        except Exception as e:
            print("Failed: ", self.pexc(e))

    async def requestCrew(self, id : int, page : int) -> dict: # request a crew info, page 0 = main page, page 1-3 = member pages
        try:
            ts = int(datetime.now(timezone.utc).replace(tzinfo=None).timestamp() * 1000)
            if page == 0:
                url = "https://game.granbluefantasy.jp/guild_other/guild_info/{}?_={}&t={}&uid={}".format(id, ts, ts+300, self.data['id'])
            else:
                url = "https://game.granbluefantasy.jp/guild_other/member_list/{}/{}?_={}&t={}&uid={}".format(page, id, ts, ts+300, self.data['id'])
            self.client.cookie_jar.clear()
            self.client.cookie_jar.update_cookies(self.data['cookie'])
            response = await self.client.get(url, headers={'Referer': 'https://game.granbluefantasy.jp/', 'Origin': 'https://game.granbluefantasy.jp', 'Host': 'game.granbluefantasy.jp', 'User-Agent': self.data['user_agent'], 'X-Requested-With': 'XMLHttpRequest', 'X-VERSION': str(self.version), 'Accept': 'application/json, text/javascript, */*; q=0.01', 'Accept-Encoding': 'gzip, deflate', 'Accept-Language': 'en', 'Connection': 'keep-alive', 'Content-Type': 'application/json'})
            async with response:
                if response.status != 200: raise Exception()
                try: self.updateCookie(response.headers['set-cookie'])
                except: pass
                return await response.json()
        except:
            return None

    async def downloadGbfg_sub(self, id: int) -> dict: # subroutine
        crew = {}
        data = {}
        for i in range(0, 4):
            get = await self.requestCrew(id, i)
            if get is None:
                if i == 0: print('Crew `{}` not found'.format(id))
                elif i == 1:
                    print('Crew `{} {}` is private'.format(id, crew['name']))
                    crew['private'] = None
                    data[str(id)] = crew
                else:
                    data[str(id)] = crew
                break
            else:
                if i == 0:
                    crew['name'] = get['guild_name']
                else:
                    if 'player' not in crew: crew['player'] = []
                    for p in get['list']:
                        crew['player'].append({'id':p['id'], 'name':p['name'], 'level':p['level'], 'is_leader':p['is_leader']})
                if i == 3:
                    data[str(id)] = crew
        return data

    async def downloadGbfg(self, *ids : int): # download all the gbfg crew member lists and make a json file in the gbfg folder
        if len(ids) == 0:
            ids = []
            for i in self.GBFG:
                ids.append(int(i))
        data = {}
        self.version = await self.getGameversion()
        if self.version is None:
            print("Impossible to get the game version currently")
            return
        
        tasks = []
        for id in ids:
            tasks.append(self.downloadGbfg_sub(id))
        res = await asyncio.gather(*tasks)
        for r in res:
            if r is not None:
                data = data | r
        if data:
            if not os.path.exists('gbfg'):
                try: os.makedirs('gbfg')
                except Exception as e:
                    print("Couldn't create a 'gbfg' directory:", self.pexc(e))
                    return
            c = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            try:
                with open('gbfg/{}.json'.format(c), 'w') as f:
                    json.dump(data, f)
                    print("'gbfg/{}.json' created".format(c))
            except:
                print("Couldn't create 'gbfg/{}.json'".format(c))
                return

    async def interface(self):
        async with self.init_client():
            # main loop
            self.loop = asyncio.get_event_loop()
            try: # unix
                self.loop.add_signal_handler(signal.SIGINT, self.exit)
            except: # windows
                signal.signal(signal.SIGINT, self.exit)
            self.check_gw(no_ongoing_check=True)
            while True:
                try:
                    print("\nMain Menu\n[0] Download Crew Ranking\n[1] Download Player Ranking\n[2] Download Crew and Player Ranking\n[3] Compile Ranking Data\n[4] Build SQL Database\n[5] Build /gbfg/ Lists\n[6] Build /gbfg/ Crew Ranking\n[7] Build /gbfg/ Player and Captain Rankings\n[8] Convert CSV into images\n[9] Do All (Only on day 4 and 5)\n[10] Advanced\n[Any] Quit")
                    i = input("Input: ")
                    print('')
                    if i == "0": await self.run(1)
                    elif i == "1": await self.run(2)
                    elif i == "2": await self.run(0)
                    elif i == "3": self.buildGW()
                    elif i == "4": self.makedb()
                    elif i == "5": self.build_crew_list()
                    elif i == "6": self.build_crew_ranking_list()
                    elif i == "7":
                        self.build_player_list()
                        self.build_player_list(captain_mode=True)
                    elif i == "8": self.leechlist_image()
                    elif i == "9":
                        if self.check_gw() in [4]:
                            print("The following will be done:")
                            print("- Rankings will be downloaded")
                            print("- Final compiled JSON will be generated")
                            print("- SQL file will be generated")
                            print("- /gbfg/ CSV will be generated")
                            if input("Input 'y' to confirm and start:").lower() == 'y':
                                print("[0/9] Downloading final day")
                                if await self.run(0):
                                    print("[1/9] Compiling Data")
                                    self.buildGW()
                                    print("[2/9] Building a SQL database")
                                    self.makedb()
                                    print("[3/9] Updating /gbfg/ data")
                                    await self.downloadGbfg()
                                    self.buildGbfgFile()
                                    print("[4/9] Building crew CSV files")
                                    self.build_crew_list()
                                    print("[5/9] Building the crew ranking CSV file")
                                    self.build_crew_ranking_list()
                                    print("[6/9] Building the player ranking CSV file")
                                    self.build_player_list()
                                    print("[7/9] Building the captain ranking CSV file")
                                    self.build_player_list(captain_mode=True)
                                    print("[8/9] Building images for .csv files")
                                    self.leechlist_image()
                                    print("[9/9] Complete")
                        else:
                            print("Invalid GW state to continue")
                            print("This setting is only usable on the last day")
                    elif i == "10":
                        while True:
                            print("\nAdvanced Menu\n[0] Merge 'gbfg.json' files\n[1] Build Temporary /gbfg/ Ranking\n[2] Download /gbfg/ player lists\n[3] Toggle Temp GW ID\n[4] Build (You) Leechlist (non-sorted)\n[Any] Quit")
                            i = input("Input: ")
                            print('')
                            if i == "0": self.buildGbfgFile()
                            elif i == "1": self.build_temp_crew_ranking_list()
                            elif i == "2": await self.downloadGbfg()
                            elif i == "3": self.toggle_temp_data()
                            elif i == "4": self.build_crew_list(you_mode=True)
                            else: break
                            self.save()
                    else: os._exit(0)
                except Exception as e:
                    print("Critical error:", self.pexc(e))
                self.save()

    def leechlist_image(self):
        if not self.imports:
            try:
                global pd
                import pandas as pd
                global plt
                import matplotlib.pyplot as plt
                global fm
                import matplotlib.font_manager as fm
                global np
                import numpy as np
                global math
                import math
                self.imports = True
            except:
                print("Can't build leechlist images")
                return
    
        # colors
        tiers = [
            { # players
                2000 : ["#ffebb3", "#f7f1e1"],
                90000 : ["#ccf0e6", "#edfffa"],
                140000 : ["#ccffb3", "#f6fff2"],
                270000 : ["#e6d5bc", "#f5eee4"],
                370000 : ["#d4c7c7", "#d4d4d4"],
                9999999999: ["#f5d0d0", "#ffb3b3"]
            },
            { # crews
                2500 : ["#ffebb3", "#f7f1e1"],
                5500 : ["#ccf0e6", "#edfffa"],
                9000 : ["#ccffb3", "#f6fff2"],
                14000 : ["#e6d5bc", "#f5eee4"],
                30000 : ["#d4c7c7", "#d4d4d4"],
                9999999999: ["#f5d0d0", "#ffb3b3"]
            }
        ]
        header_color = "#006600"
        first_col_color = ["#f7eee1", "#ffdeb3"]
        na_color = ["#f5d0d0", "#ffb3b3"]

        # Get csv list
        csv_files = glob.glob("*.csv")

        if len(csv_files) == 0: return

        # make output folder
        output_folder = "images"
        try: os.mkdir(output_folder)
        except: pass

        # Load the font using FontManager
        prop = fm.FontProperties(fname='C:\\Windows\\Fonts\\INSTALL_THIS_UNICODE_FONT.ttf')

        for filename in csv_files:
            print("Opening", filename)
            try:
                # Load csv
                df = pd.read_csv(filename)

                if len(df) > 50: # for Players.csv or History.csv
                    if filename.endswith('_Players.csv') or filename.endswith('_Captains.csv'):
                        isplayerfile = True
                        player_index = 13
                        limit = 300 # entry limit
                    elif '_History_' in filename:
                        isplayerfile = True
                        player_index = 13
                        limit = 300
                    if len(df) > limit:
                        df = df.head(limit)
                    part_count = int(math.ceil(len(df) / 50.0))
                    
                    index = 0
                    parts = [df.iloc[:50]]
                    for i in range(1, part_count):
                        parts.append(df.iloc[50*i:min(len(df), 50*(i+1))])
                        parts[-1].reset_index(drop=True, inplace=True) # reset index of subsequent parts
                    df = pd.concat(parts, axis=1) # concatenate parts
                else:
                    isplayerfile = False
                    player_index = 16
                iscrewfile = (filename.endswith('_Crews.csv'))

                # Replace NaN values with an empty string
                df.replace(np.nan, '', inplace=True)

                # Create a figure and axis for plotting
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.axis('off')

                # Plot the table using ax.table()
                table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='left', loc='center')
                table.auto_set_font_size(False)
                table.set_fontsize(12)
                table.scale(1, 1.5)

                empty_lines = set() # for player files

                element_count = 0
                id_col = set()
                guild_col = set()
                name_col = set()
                best_col = set()
                # read first row
                for key, cell in table.get_celld().items():
                    if key[0] != 0: continue
                    cell_text = cell.get_text().get_text()
                    if cell_text.endswith('.1') or cell_text.endswith('.2'):
                        cell.get_text().set_text(cell_text[:-2])
                    if cell_text == "id": id_col.add(key[1])
                    elif cell_text == "guild": guild_col.add(key[1])
                    elif cell_text == "name": name_col.add(key[1])
                    elif cell_text == "best ranked" or cell_text == "best contrib.": best_col.add(key[1])

                # Set the font properties for each text object within the cells
                for key, cell in table.get_celld().items():
                    cell.set_text_props(fontproperties=prop)
                    cell.set_edgecolor('none')
                    # Format float numbers as integers, with thousand separators
                    cell_text = cell.get_text().get_text()
                    if cell_text.replace(".", "").isnumeric():
                        if key[1] in id_col: # ID formatting
                            cell.get_text().set_text(str(int(float(cell_text))))
                        else:
                            cell.get_text().set_text('{:,}'.format(int(float(cell_text))))
                        if key[1] == 0: # counting number of elements (first column)
                            element_count = max(element_count, int(cell.get_text().get_text()))
                    if isplayerfile and (key[1] % player_index) == 0 and key[1] >= player_index and cell_text == "":
                        empty_lines.add("{}-{}".format(key[0], key[1] // player_index))

                ldf = len(df) # data length
                for key, cell in table.get_celld().items():
                    # Format other strings
                    row_index, col_index = key
                    if isplayerfile:
                        col_part = col_index // player_index
                        col_index = col_index % player_index
                    cell_text = cell.get_text().get_text()
                    if row_index == 0 and (col_index == 0 or (isplayerfile and col_index == 0)): # Hide the content of the first cell
                        cell.get_text().set_text("")
                    elif cell_text == "":
                        if isplayerfile and "{}-{}".format(row_index, col_part) in empty_lines:
                            pass # do nothing
                        elif row_index <= element_count:
                            cell.get_text().set_text("n/a")
                    elif cell_text == "id":
                        cell.get_text().set_text("ID")
                    else:
                        if col_index in guild_col and row_index > 0: # guild column
                            pass # no formatting
                        elif col_index in best_col and row_index > 0: # best column (History.csv)
                            pass # no formatting
                        elif col_index in name_col and row_index > 0: # name
                            pass # no formatting
                        else:
                            cell.get_text().set_text(cell_text.capitalize().replace('& d', '& D'))

                    # Alternating row colors
                    if isplayerfile:
                        row_index, col_index = key
                        index = (row_index - 1) + (col_index // player_index) * (ldf + 1)
                    else:
                        index = row_index
                    if row_index == 0: # header
                        table[key].set_facecolor(header_color)
                        table[key].get_text().set_color('#ffffff')
                    elif row_index <= element_count:
                        color_index = (index + 1) % 2
                        cell_text = cell.get_text().get_text()
                        if col_index == 0 or (isplayerfile and (col_index % player_index) == 0): # first column
                            table[key].set_facecolor(first_col_color[color_index])
                        elif cell.get_text().get_text() == "n/a":
                            table[key].set_facecolor(na_color[color_index])
                        else:
                            try: ranking = int(table._cells[(row_index, col_index + 1 - col_index % player_index)]._text.get_text().replace(',', ''))
                            except: ranking = 9999999998
                            for k, v in tiers[iscrewfile].items():
                                if ranking < k:
                                    table[key].set_facecolor(v[color_index])
                                    break

                # Automatically adjust the cell size to fit the text
                table.auto_set_column_width(col=list(range(len(df.columns))))

                # Save the image
                plt.savefig(output_folder + '/' + filename.replace('.csv', '.png'), bbox_inches='tight')
                plt.close()
                print(filename.replace('.csv', '.png'), "done")
            except Exception as e:
                self.pexc(e)
                print("Failed to process", filename)

if __name__ == "__main__":
    asyncio.run(Scraper().interface())