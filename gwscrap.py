from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
from urllib import request, parse
from socket import timeout
import json
import zlib
import time
import re
from threading import Thread
from queue import Queue
import signal
import sqlite3
import csv
import os
from os import listdir
from os.path import isfile, join

class Scrapper():
    def __init__(self, gw_num : int): # constructor requires the gw number
        if gw_num < 1 or gw_num > 999: raise Exception("Invalid GW ID")
        self.gbfg_ids = ['418206','432330','472465','518173','581111','1010961','705648','841064','745085','1317803','645927','844716','599992','940560','940700','977866','1036007','1049216','1141898','1161924','588156','1593480','1586134','1580990','1629318','632242','678459','1601132','1380234']
        self.gw = gw_num
        self.max_threads = 100 # change this if needed
        # preparing urls
        base_url = "http://game.granbluefantasy.jp/teamraid" + str(gw_num).zfill(3)
        self.crew_url = base_url + "/rest/ranking/totalguild/detail/{}/0?_={}&t={}&uid={}"
        self.player_url = base_url + "/rest_ranking_user/detail/{}/0?_={}&t={}&uid={}"
        # empty save data
        self.data = {'id':0, 'cookie':'', 'user_agent':''}
        self.version = None
        self.vregex = re.compile("Game\.version = \"(\d+)\";")
        # load our data
        if not self.load():
            self.save() # failed? we make an empty file
            print("No 'config.json' file found.\nAn empty 'config.json' files has been created\nPlease fill it with your cookie, user agent and GBF profile id")
            exit(0)
        # for Ctrl+C
        signal.signal(signal.SIGINT, self.exit)

    def exit(self): # called by ctrl+C
        print("Saving...")
        self.save()

    def load(self): # load cookie and stuff
        try:
            with open('config.json') as f:
                data = json.load(f)
                if 'id' not in self.data or 'cookie' not in self.data or 'user_agent' not in self.data: raise Exception("Missing settings in config.json")
                self.data = data
                return True
        except Exception as e:
            print('load(): ' + str(e))
            return False

    def save(self): # save
        try:
            with open('config.json', 'w') as outfile:
                json.dump(self.data, outfile)
            return True
        except Exception as e:
            print('save(): ' + str(e))
            return False

    def writeFile(self, data, name): # write our scrapped ranking
        try:
            with open(name, 'w') as outfile:
                json.dump(data, outfile)
            return True
        except Exception as e:
            print('writeFile(): ' + str(e))
            return False

    def getGameversion(self): # get the game version
        try:
            req = request.Request('http://game.granbluefantasy.jp/')
            req.add_header('Host', 'game.granbluefantasy.jp')
            req.add_header('User-Agent', self.data['user_agent'])
            req.add_header('Accept-Encoding', 'gzip, deflate')
            req.add_header('Accept-Language', 'en')
            req.add_header('Connection', 'keep-alive')
            url_handle = request.urlopen(req)
            res = self.vregex.findall(str(zlib.decompress(url_handle.read(), 16+zlib.MAX_WBITS)))
            return int(res[0]) # to check if digit
        except:
            return None

    def updateCookie(self, new): # update the cookie string
        A = self.data['cookie'].split(';')
        B = new.split(';')
        for c in B:
            tA = c.split('=')
            if tA[0][0] == " ": tA[0] = tA[0][1:]
            f = False
            for i in range(0, len(A)):
                tB = A[i].split('=')
                if tB[0][0] == " ": tB[0] = tB[0][1:]
                if tA[0] == tB[0]:
                    A[i] = c
                    f = True
                    break
        self.data['cookie'] = ";".join(A)

    def requestRanking(self, page, crew = True): # request a ranking page and return the data
        try:
            ts = int(datetime.utcnow().timestamp() * 1000)
            if crew: req = request.Request(self.crew_url.format(page, ts, ts+300, self.data['id']))
            else: req = request.Request(self.player_url.format(page, ts, ts+300, self.data['id']))
            req.add_header('Cookie', self.data['cookie'])
            req.add_header('Referer', 'http://game.granbluefantasy.jp/')
            req.add_header('Origin', 'http://game.granbluefantasy.jp')
            req.add_header('Host', 'game.granbluefantasy.jp')
            req.add_header('User-Agent', self.data['user_agent'])
            req.add_header('X-Requested-With', 'XMLHttpRequest')
            req.add_header('X-VERSION', self.version)
            req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
            req.add_header('Accept-Encoding', 'gzip, deflate')
            req.add_header('Accept-Language', 'en')
            req.add_header('Connection', 'keep-alive')
            req.add_header('Content-Type', 'application/json')
            url_handle = request.urlopen(req)
            try: self.updateCookie(url_handle.info()['Set-Cookie'])
            except: pass
            decompressed_data=zlib.decompress(url_handle.read(), 16+zlib.MAX_WBITS)
            return json.loads(decompressed_data)
        except:
            return None

    def crewProcess(self, q, results): # thread for crew ranking
        while not q.empty():
            page = q.get()
            data = None
            while data is None:
                data = self.requestRanking(page, True)
                if data is None: print("Crew: Error on page", page)
            for i in range(0, len(data['list'])):
                results[int(data['list'][i]['ranking'])-1] = data['list'][i]
            q.task_done()
        return True

    def playerProcess(self, q, results): # thread for player ranking (same thing, I copypasted)
        while not q.empty():
            page = q.get()
            data = None
            while data is None:
                data = self.requestRanking(page, False)
                if data is None: print("Player: Error on page", page)
            for i in range(0, len(data['list'])):
                results[int(data['list'][i]['rank'])-1] = data['list'][i]
            q.task_done()
        return True

    def run(self, mode = 0): # main loop. 0 = both crews and players, 1 = crews, 2 = players
        # user check
        input("Make sure you won't overwrite a file (Press anything to continue): ")
        # check the game version
        self.version = self.getGameversion()
        if self.version is None:
            print("Impossible to get the game version currently")
            return
        print("Current game version is", self.version)

        if mode == 0 or mode == 1:
            # crew ranking
            data = self.requestRanking(1, True) # get the first page
            if data is None:
                print("Can't access the crew ranking")
                self.save()
                return
            count = int(data['count']) # number of crews
            last = data['last'] # number of pages
            print("Crew ranking has {} crews and {} pages".format(count, last))
            results = [{} for x in range(count)] # make a big array
            for i in range(0, len(data['list'])): # fill the first slots with the first page data
                results[i] = data['list'][i]

            q = Queue()
            for i in range(2, last+1): # queue the pages to retrieve
                q.put(i)

            print("Scrapping...")
            for i in range(self.max_threads): # make lot of threads
                worker = Thread(target=self.crewProcess, args=(q, results))
                worker.setDaemon(True)
                worker.start()
            q.join() # wait for them to finish

            self.writeFile(results, 'GW{}_crew.json'.format(self.gw)) # save the result
            print("Done, saved to 'GW{}_crew.json'".format(self.gw))

        if mode == 0 or mode == 2:
            # player ranking. exact same thing, I lazily copypasted.
            data = self.requestRanking(1, False)
            if data is None:
                print("Can't access the player ranking")
                self.save()
                return
            count = int(data['count'])
            last = data['last']
            print("Crew ranking has {} players and {} pages".format(count, last))
            results = [{} for x in range(count)]
            for i in range(0, len(data['list'])):
                results[i] = data['list'][i]

            q = Queue()
            for i in range(2, last+1):
                q.put(i)

            print("Scrapping...")
            for i in range(self.max_threads):
                worker = Thread(target=self.playerProcess, args=(q, results))
                worker.setDaemon(True)
                worker.start()
            q.join()

            self.writeFile(results, 'GW{}_player.json'.format(self.gw))
            print("Done, saved to 'GW{}_player.json'".format(self.gw))
            self.save()

    def buildGW(self, mode = 0): # build a .json compiling all the data withing json named with the 'days' suffix
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
                    print(e)
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
                    print(e)
            self.writeFile(results, 'GW{}_player_full.json'.format(self.gw))
            print("Done, saved to 'GW{}_player_full.json'".format(self.gw))

    def makedb(self): # make a SQL file (useful for searching the whole thing)
        try:
            print("Building Database...")
            try:
                with open('GW{}_player_full.json'.format(self.gw)) as f:
                    pdata = json.load(f)
                with open('GW{}_crew_full.json'.format(self.gw)) as f:
                    cdata = json.load(f)
            except Exception as ex:
                print("Error:", ex)
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
            print('makedb(): ' + str(e))
            return False

    def makebotdb(self, mode = 0): # make a SQL file (useful for searching the whole thing)
        try:
            print("Building Database...")
            try:
                with open('GW{}_crew_full.json'.format(self.gw)) as f:
                    cdata = json.load(f)
                with open('GW{}_player_full.json'.format(self.gw)) as f:
                    pdata = json.load(f)
            except Exception as ex:
                print("Error:", ex)
                return
            conn = sqlite3.connect('GW.sql'.format(self.gw))
            c = conn.cursor()
            c.execute('CREATE TABLE GW (id)')
            c.execute("INSERT INTO GW VALUES ({})".format(self.gw))
            c.execute('CREATE TABLE crews (ranking int, id int, name text, preliminaries int, day1 int, total_1 int, day_2 int, total_2 int, day_3 int, total_3 int, day_4 int, total_4 int)')
            for id in cdata:
                c.execute("INSERT INTO crews VALUES ({},{},'{}',{},{},{},{},{},{},{},{},{})".format(cdata[id].get('ranking', 'NULL'), id, cdata[id]['name'].replace("'", "''"), cdata[id].get('prelim', 'NULL'), cdata[id].get('delta_d1', 'NULL'), cdata[id].get('d1', 'NULL'), cdata[id].get('delta_d2', 'NULL'), cdata[id].get('d2', 'NULL'), cdata[id].get('delta_d3', 'NULL'), cdata[id].get('d3', 'NULL'), cdata[id].get('delta_d4', 'NULL'), cdata[id].get('d4', 'NULL')))
            c.execute('CREATE TABLE players (ranking int, id int, name text, total_4 int)')
            for id in pdata:
                if mode == 1:
                    c.execute("INSERT INTO players VALUES ({},{},'{}',{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id].get('prelim', 'NULL')))
                elif mode == 2:
                    c.execute("INSERT INTO players VALUES ({},{},'{}',{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id].get('d1', 'NULL')))
                elif mode == 3:
                    c.execute("INSERT INTO players VALUES ({},{},'{}',{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id].get('d2', 'NULL')))
                elif mode == 4:
                    c.execute("INSERT INTO players VALUES ({},{},'{}',{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id].get('d3', 'NULL')))
                elif (mode == 0 and pdata[id].get('rank', 'NULL') != 'NULL') or (mode == 1):
                    c.execute("INSERT INTO players VALUES ({},{},'{}',{})".format(pdata[id].get('rank', 'NULL'), id, pdata[id]['name'].replace("'", "''"), pdata[id].get('d4', 'NULL')))
            conn.commit()
            conn.close()
            print('Done')
            return True
        except Exception as e:
            print('makebotdb(): ' + str(e))
            return False

    def build_crew_list(self, temp=None): # build the gbfg leechlists on a .csv format
        remove_punctuation_map = dict((ord(char), None) for char in '\/*?:"<>|')
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_player_full.json'.format(self.gw)) as f:
                players = json.load(f)
        except Exception as e:
            print("Error:", e)
            return
        # one crew by one
        for c in gbfg:
            if 'private' in gbfg[c]: continue # ignore private crews
            with open("GW{}_{}.csv".format(self.gw, gbfg[c]['name'].translate(remove_punctuation_map)), 'w', newline='', encoding="utf-8") as csvfile:
                llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
                llwriter.writerow(["", "#", "id", "name", "rank", "battle", "preliminaries", "interlude & day 1", "total 1", "day 2", "total 2", "day 3", "total 3", "day 4", "total 4"])
                l = []
                for p in gbfg[c]['player']:
                    if str(p['id']) in players:
                        if p['is_leader']: players[str(p['id'])]['name'] += " (c)"
                        l.append(players[str(p['id'])])
                        l[-1]['id'] = str(p['id'])
                    else: l.append(p)
                crew_size = len(l)
                total = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
                for i in range(0, crew_size):
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
                    if idx != -1:
                        llwriter.writerow([str(i+1), l[idx].get('rank', 'n/a'), l[idx]['id'], l[idx]['name'], l[idx]['level'], l[idx].get('defeat', 'n/a'), l[idx].get('prelim', 'n/a'), l[idx].get('delta_d1', 'n/a'), l[idx].get('d1', 'n/a'), l[idx].get('delta_d2', 'n/a'), l[idx].get('d2', 'n/a'), l[idx].get('delta_d3', 'n/a'), l[idx].get('d3', 'n/a'), l[idx].get('delta_d4', 'n/a'), l[idx].get('d4', 'n/a')])
                        total[0] += int(l[idx]['level'])
                        total[1] += int(l[idx].get('prelim', '0'))
                        total[2] += int(l[idx].get('delta_d1', '0'))
                        total[3] += int(l[idx].get('d1', '0'))
                        total[4] += int(l[idx].get('delta_d2', '0'))
                        total[5] += int(l[idx].get('d2', '0'))
                        total[6] += int(l[idx].get('delta_d3', '0'))
                        total[7] += int(l[idx].get('d3', '0'))
                        total[8] += int(l[idx].get('delta_d4', '0'))
                        total[9] += int(l[idx].get('d4', '0'))
                        l.pop(idx)
                    else:
                        for p in gbfg[c]['player']:
                            if l[0]['id'] == p['id']:
                                if p['is_leader']: l[0]['name'] += " (c)"
                                break
                        llwriter.writerow([str(i+1), 'n/a', l[0]['id'], l[0]['name'], l[0]['level'], 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a'])
                        total[0] += int(l[0]['level'])
                        l.pop(0)
                llwriter.writerow(['', '', '', 'average', str(total[0]//crew_size), '', '', '', '', '', '', '', '', '', ''])
                llwriter.writerow(['', '', '', 'total', '', '', str(total[1]), str(total[2]), str(total[3]), str(total[4]), str(total[5]), str(total[6]), str(total[7]), str(total[8]), str(total[9])])
                llwriter.writerow(['', '', '', '', '', '', '', '', '', '', '', '', '', '', ''])
                llwriter.writerow(['', 'guild', str(c), gbfg[c]['name'], '', '', '', '', '', '', '', '', '', '', ''])
                print("GW{}_{}.csv: Done".format(self.gw, gbfg[c]['name'].translate(remove_punctuation_map)))

    def build_temp_crew_ranking_list(self): # same thing but while gw is on going (work a bit differently, useful for scouting enemies)
        try:
            with open('GW{}_crew_full.json'.format(self.gw)) as f:
                crews = json.load(f)
        except Exception as e:
            print("Error:", e)
            return
        with open("GW{}_Crews.csv".format(self.gw), 'w', newline='', encoding="utf-8") as csvfile:
            llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
            llwriter.writerow(["", "#", "id", "name", "preliminaries", "day 1", "day 2", "day 3", "day 4", "total"])
            ranked = []
            unranked = []
            for c in self.gbfg_ids:
                if c in crews:
                    row = [crews[c].get('ranking', 'n/a'), c, crews[c]['name']]
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

    def build_crew_ranking_list(self): # build the ranking of all the gbfg crews
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_crew_full.json'.format(self.gw)) as f:
                crews = json.load(f)
        except Exception as e:
            print("Error:", e)
            return
        with open("GW{}_Crews.csv".format(self.gw), 'w', newline='', encoding="utf-8") as csvfile:
            llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
            llwriter.writerow(["", "#", "id", "name", "preliminaries", "day 1", "day 2", "day 3", "day 4", "final"])
            ranked = []
            unranked = []
            for c in gbfg:
                row = ['', c, gbfg[c]['name']]
                if c in crews:
                    row[0] = crews[c].get('ranking', 'n/a')
                    row.append(crews[c].get('prelim', 'n/a'))
                    row.append(crews[c].get('delta_d1', 'n/a'))
                    row.append(crews[c].get('delta_d2', 'n/a'))
                    row.append(crews[c].get('delta_d3', 'n/a'))
                    row.append(crews[c].get('delta_d4', 'n/a'))
                    row.append(crews[c].get('d4', 'n/a'))
                else: row = ['n/a', c, gbfg[c]['name'], 'n/a', 'n/a', 'n/a', 'n/a', 'n/a', 'n/a']
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

    def build_player_list(self):  # build the ranking of all the gbfg players
        try:
            with open('gbfg.json') as f:
                gbfg = json.load(f)
            with open('GW{}_player_full.json'.format(self.gw)) as f:
                players = json.load(f)
        except Exception as e:
            print("Error:", e)
            return
        l = []
        for c in gbfg:
            if 'private' in gbfg[c]: continue
            for p in gbfg[c]['player']:
                if str(p['id']) in players and 'rank' in players[str(p['id'])]:
                    x = 0
                    for x in range(0, len(l)):
                        if 'rank' in l[x] and int(players[str(p['id'])]['rank']) < int(l[x]['rank']):
                            l.insert(x, players[str(p['id'])])
                            l[x]['id'] = str(p['id'])
                            l[x]['guild'] = gbfg[c]['name']
                            break
                        elif x == len(l) - 1:
                            l.append(players[str(p['id'])])
                            l[-1]['id'] = str(p['id'])
                            l[-1]['guild'] = gbfg[c]['name']
                    if len(l) == 0:
                        l.append(players[str(p['id'])])
                        l[-1]['id'] = str(p['id'])
                        l[-1]['guild'] = gbfg[c]['name']
        if len(l) > 0:
            with open("GW{}_Players.csv".format(self.gw), 'w', newline='', encoding="utf-8") as csvfile:
                llwriter = csv.writer(csvfile, delimiter=',', quotechar='"', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
                llwriter.writerow(["", "#", "id", "name", "guild", "rank", "battle", "preliminaries", "interlude & day 1", "total 1", "day 2", "total 2", "day 3", "total 3", "day 4", "total 4"])
                for i in range(0, len(l)):
                    llwriter.writerow([str(i+1), l[i].get('rank', 'n/a'), l[i]['id'], l[i]['name'], l[i]['guild'], l[i]['level'], l[i].get('defeat', 'n/a'), l[i].get('prelim', 'n/a'), l[i].get('delta_d1', 'n/a'), l[i].get('d1', 'n/a'), l[i].get('delta_d2', 'n/a'), l[i].get('d2', 'n/a'), l[i].get('delta_d3', 'n/a'), l[i].get('d3', 'n/a'), l[i].get('delta_d4', 'n/a'), l[i].get('d4', 'n/a')])
            print("GW{}_Players.csv: Done".format(self.gw))

    def buildGbfgFile(self): # check the gbfg folder for any json files and fuse the data into one
        # gbfg.json is used in other functions, it contains the crew member lists
        try:
            files = [f for f in listdir('gbfg') if isfile(join('gbfg', f))]
            final = {}
            for fn in files:
                with open('gbfg/{}'.format(fn)) as f:
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
            print("Failed: ", e)

    def buildRequest(self, url, payload=None): # to request stuff to gbf
        if payload is None:
            req = request.Request(url)
        else:
            req = request.Request(url, data=str(json.dumps(payload)).encode('utf-8'))
        req.add_header('Cookie', self.data['cookie'])
        req.add_header('Referer', 'http://game.granbluefantasy.jp/')
        req.add_header('Origin', 'http://game.granbluefantasy.jp')
        req.add_header('Host', 'game.granbluefantasy.jp')
        req.add_header('User-Agent', str(self.data['user_agent']))
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('X-VERSION', str(self.version))
        req.add_header('Accept', 'application/json, text/javascript, */*; q=0.01')
        req.add_header('Accept-Encoding', 'gzip, deflate')
        req.add_header('Accept-Language', 'en')
        req.add_header('Connection', 'keep-alive')
        req.add_header('Content-Type', 'application/json')
        return req

    def requestCrew(self, id, page): # request a crew info, page 0 = main page, page 1-3 = member pages
        try:
            ts = int(datetime.utcnow().timestamp() * 1000)
            if page == 0:
                req = self.buildRequest("http://game.granbluefantasy.jp/guild_other/guild_info/{}?_={}&t={}&uid={}".format(id, ts, ts+300, self.data['id']))
            else:
                req = self.buildRequest("http://game.granbluefantasy.jp/guild_other/member_list/{}/{}?_={}&t={}&uid={}".format(page, id, ts, ts+300, self.data['id']))
            url_handle = request.urlopen(req)
            try: self.updateCookie(url_handle.info()['Set-Cookie'])
            except: pass
            return json.loads(zlib.decompress(url_handle.read(), 16+zlib.MAX_WBITS))
        except Exception as e:
            if str(e) != "Expecting value: line 1 column 1 (char 0)":
                print(e)
            return None

    def downloadGbfg(self, *ids : int): # download all the gbfg crew member lists and make a json file in the gbfg folder
        if len(ids) == 0:
            ids = []
            for i in self.gbfg_ids:
                ids.append(int(i))
        data = {}
        self.version = self.getGameversion()
        if self.version is None:
            print("Impossible to get the game version currently")
            return
        for id in ids:
            crew = {}
            for i in range(0, 4):
                get = self.requestCrew(id, i)
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
        if data:
            if not os.path.exists('gbfg'):
                try: os.makedirs('gbfg')
                except Exception as e:
                    print("Couldn't create a 'gbfg' directory:", e)
                    return
            c = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            try:
                with open('gbfg/{}.json'.format(c), 'w') as f:
                    json.dump(data, f)
                    print("'gbfg/{}.json' created".format(c))
            except Exception as e:
                print("Couldn't create 'gbfg/{}.json'".format(c))
                return

# we start here
print("GW Ranking Scrapper 1.6")
# gw num
while True:
    try:
        i = int(input("Please input the GW number: "))
        break
    except:
        pass
# init
try:
    scrapper = Scrapper(i)
except Exception as e:
    print(e)
    exit(0)
# main loop
while True:
    try:
        print("\nMain Menu\n[0] Download Crew\n[1] Download Player\n[2] Download All\n[3] Compile Crew Data\n[4] Compile Player Data\n[5] Build Database\n[6] Build Crew Lists\n[7] Build Crew Ranking\n[8] Build Player Ranking\n[9] Compile and Build all\n[10] Advanced\n[Any] Quit")
        i = input("Input: ")
        print('')
        if i == "0": scrapper.run(1)
        elif i == "1": scrapper.run(2)
        elif i == "2": scrapper.run(0)
        elif i == "3": scrapper.buildGW(1)
        elif i == "4": scrapper.buildGW(2)
        elif i == "5": scrapper.makedb()
        elif i == "6": scrapper.build_crew_list()
        elif i == "7": scrapper.build_crew_ranking_list()
        elif i == "8": scrapper.build_player_list()
        elif i == "9":
            print("[0/6] Compiling Data")
            scrapper.buildGW()
            print("[1/6] Building a SQL database")
            scrapper.makedb()
            print("[2/6] Updating /gbfg/ data")
            scrapper.downloadGbfg()
            scrapper.buildGbfgFile()
            print("[3/6] Building crew .csv files")
            scrapper.build_crew_list()
            print("[4/6] Building the crew ranking .csv file")
            scrapper.build_crew_ranking_list()
            print("[5/6] Building the player ranking .csv file")
            scrapper.build_player_list()
            print("[6/6] Complete")
        elif i == "10":
            while True:
                print("\nAdvanced Menu\n[0] Merge 'gbfg.json' files\n[1] Build Temporary Crew Lists\n[2] Build Temporary /gbfg/ Ranking\n[3] Download /gbfg/ member list\n[4] Download a crew member list\n[5] Make Temporary MizaBOT database\n[6] Make Final MizaBOT database\n[Any] Quit")
                i = input("Input: ")
                print('')
                if i == "0": scrapper.buildGbfgFile()
                elif i == "1":
                    days = ['prelim', 'd1', 'd2', 'd3']
                    print("Input the current day (Leave blank to cancel):", days)
                    i = input("Input: ")
                    if i == "": pass
                    elif i not in days: print("Invalid day")
                    else: scrapper.build_crew_list(i)
                elif i == "2": scrapper.build_temp_crew_ranking_list()
                elif i == "3": scrapper.downloadGbfg()
                elif i == "3": scrapper.downloadGbfg()
                elif i == "4":
                    print("Please input the crew(s) id (Leave blank to cancel)")
                    i = input("Input: ")
                    if i == "": pass
                    else:
                        try:
                            i = i.split()
                            print(i)
                            l = []
                            for x in i: l.append(int(x))
                            print(l)
                            scrapper.downloadGbfg(*l)
                        except: print("Please input a number")
                elif i == "5": 
                    days = ['prelim', 'd1', 'd2', 'd3']
                    print("Input the current day (Leave blank to cancel):", days)
                    i = input("Input: ")
                    if i == "": pass
                    elif i not in days: print("Invalid day")
                    else: scrapper.makebotdb(days.index(i) + 1)
                elif i == "6": scrapper.makebotdb(0)
                else: break
                scrapper.save()
        else: exit(0)
    except Exception as e:
        print("Critical error:", e)
    scrapper.save()