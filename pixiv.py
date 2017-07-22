from client import WebClient
import sys, math, json

def uprint(string):
    sys.stdout.write('\r' + string)
    sys.stdout.flush()


class PixivClient(WebClient):

    def __init__(self, username, password):
        WebClient.__init__(self)
        self.users = {}
        self.works = {}
        self.loadCache()
        
        if self.login(username, password) != 200: # not enough?
            raise RuntimeError("Login failed. Wrong username and/or password?")

    def dumpCache(self): 
        json.dump([self.users, self.works], self.archiver.file("cache", 'w'))

    def loadCache(self):
        try: self.users, self.works = json.load(self.archiver.file("cache", 'r'))
        except: print("Cache load failed")

    def _countPages(self, url, perpage):
        self.traverse(url)
        num_items = int(self.parseElement("span class=count-badge").string.split()[0])
        return math.ceil(num_items / perpage)
        
    def _scrapeFollowedUsers(self):
        baseurl = "https://www.pixiv.net/bookmark.php?type=user&rest=show"
        num_pages = self._countPages(baseurl, 48)
           
        for p in range(1, num_pages + 1):
            uprint("Scraping followed users... (%.0f %%)" % (p / num_pages * 100))
            self.traverse(baseurl + "&p=" + str(p))
            udata = self.parseAllElements("a", "div class=userdata")
            
            new = []
            for u in udata:
                if u['data-user_id'] not in self.users:
                    self.users[u['data-user_id']] = {}
                    new.append(u['data-user_id'])
       
            rm = []
            for uid in [u['data-user_id'] for u in udata]:
                if uid not in self.users:
                    del self.users[uid]
                    rm.append(uid)

        print() # done
        return new

    def _scrapeUserInfo(self, userid):
        baseurl = "https://www.pixiv.net/member_illust.php?id=" + userid + "&type=all"
        num_pages = self._countPages(baseurl, 20)

        self.users[userid].update({
            'name': self.parseElement("h1 class=user").string,
            'image': self.parseElement("img class=user-image")['src']
        })
        if 'illust' not in self.users[userid]: self.users[userid]['illust'] = {}

        for p in range(1, num_pages + 1):
            self.traverse(baseurl + "&p=" + str(p))
            uprint("Scraping user " + userid + "'s information (%.0f %%)" % (p / num_pages * 100))

            for i in self.parseAllElements("a class=work"):
                entry = {'url': "https://www.pixiv.net" + i['href'], 
                         'classes': i['class']}
                i = i.find("img")
                workid = i['data-id']
                entry['thumb'] = i['data-src']
                entry['tags'] = i['data-tags'].split()
                if self._getWorkStatus(workid) not in ["info", "okay"]:
                    entry['images'] = []
                    entry['type'] = "?"
                    entry['status'] = "none"
                self.users[userid]['illust'][i['data-id']].update(entry)

        for i in self.users[userid]['illust']:
            self.works[i] = userid

        print() # done

    def updateAllUserInfo(self):
        self._scrapeFollowedUsers()
        for i, uid in enumerate(self.users):
            try:
                self._scrapeUserInfo(uid)
                self._scrapeUserIllust(uid)
            except Exception as e:
                self.archiver.log(str(e))
            print("Updated %s's info (%d / %d)" % (self.users[uid]['name'], i + 1, len(self.users)))
        
    def _scrapeUserIllust(self, userid):
        illust = self.users[userid]['illust']
        for num, (workid, entry) in enumerate(illust.items()):
            if self._getWorkStatus(workid) in ["info", "okay"]: continue
            
            uprint("Scraping user " + userid + "'s illustration information (%.0f %%)" % ((num + 1) / len(illust) * 100))
            self.traverse(entry['url'])

            if "rtl" in entry['classes']:
                entry['type'] = "rtl"

            elif "multiple" in entry['classes']:
                entry['type'] = "manga"
                self.traverse("https://www.pixiv.net/member_illust.php?mode=manga&illust_id=" + workid)
                bigbase = "http://www.pixiv.net" + self.parseElement("a class=full-size-container")['href']
                for i in range(0, int(self.parseElement("span class=total").string)):
                    self.traverse(bigbase[:-1] + str(i))
                    entry['images'].append(self.parseElement("img")['src'])

            elif "ugoku-illust" in entry['classes']:
                entry['type'] = "animation"
                info = self.executeJS("ugoira.js")[-1].split(',')
                entry['images'] = [info[0].replace("600x600", "1920x1080")]
                entry['delays'] = info[1:]

            else: # work, _work, manga, ''
                entry['type'] = "normal"
                url = self.parseElement("img class=original-image").get('data-src', "")
                if not url:
                    self.setReferer(entry['url'])
                    self.traverse(entry['url'].replace("medium", "big"))
                    url = self.parseElement("img").get("src", "")
                    if not url or "img-original" not in url:
                        url = "???"
                entry['images'] = [url]

            entry['status'] = "info"
            self.users[userid]['illust'][workid] = entry
            
        print() # done

    def printUserInfo(self, userid):
        user = self.users[userid]
        for i, work in user['illust'].items():
            print(i, work['status'], work['type'], work['url'])
        print(user['name'] + " (" + userid + ") - " + str(len(user['illust'])) + " illustrations")


    def _getWorkStatus(self, workid):
        try: 
            userid = self.works[workid]
            return self.users[userid]['illust'][workid]['status']
        except:
            return ""

    def updateUserArchive(self, userid):
        userpath = "Following/" + self.users[userid]['name']
        self._updateUserImage(userid, userpath)
        dl = {workid: entry for workid, entry in self.users[userid]['illust'].items() if entry['status'] != "okay"}

        for num, (workid, entry) in enumerate(dl.items()):
            uprint("Downloading user " + userid + "'s illustrations (%d / %d)" % (num + 1, len(dl)))
            try: status = self._archiveIllust(workid, userpath + "/Illustrations")
            except Exception as e:
                self.archiver.log(str(e))
                status = "fail"
            self.users[userid]['illust'][workid]['status'] = status
            
        print() # done

    def _updateUserImage(self, userid, path):
        path = self.archiver.folder(path)
        url = self.users[userid]['image']
        ext = '.' + url.split('.')[-1]
        self.setReferer(url)
        try: self.saveFile(url, path + userid + ext)
        except Exception as e:
            self.archiver.log(str(e))

    def findIncompeteArchives(self, status = "okay"):
        uids = []
        for uid, entry in self.users.items():
            for workid in entry['illust']:
                if self._getWorkStatus(workid) not in [status, "typ?"]:
                    uids.append(uid)
                    break
        return uids

    def _archiveIllust(self, workid, path):
        userid = self.works[workid]
        entry = self.users[userid]['illust'][workid]
        folder = self.archiver.folder(path)

        if entry['type'] == "manga":
            for i in entry['images']:
                if self.saveFile(i, folder + i.split('/')[-1]) != 200:
                    return "fail" # do exceptions ffs

        elif entry['type'] == "animation":
            self.setReferer(entry['url'])
            if self.saveFile(entry['images'][0], "temp/ani.zip") != 200:
                return "fail"
            self.archiver.zipToAnimation("temp/ani.zip", folder, workid, [int(i) for i in entry['delays']])

        elif entry['type'] == "normal":
            self.setReferer(entry['url'])
            filename = entry['images'][0].split('/')[-1]
            if self.saveFile(entry['images'][0], folder + filename) != 200:
                return "fail"
        
        else:
            return "typ?"

        return "okay"
