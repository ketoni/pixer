import time, requests
from bs4 import BeautifulSoup
from abc import ABCMeta, abstractmethod

from archiver import Archiver

class WebClient(metaclass=ABCMeta):

    def __init__(self):
        self.session = requests.Session()
        self.archiver = Archiver()
        self.response = ""
        self.html_soup = ""

    @abstractmethod
    def login():
        pass

    def tryGet(self, url, trials = 5):
        while trials:
            try: return self.session.get(url)
            except Exception as e:
                self.archiver.log(str(e))
                time.sleep(1)
                trials -= 1
        if not trials: raise RuntimeError("GET to " + url + " failed after " + str(trials) + " trials")

    def traverse(self, url):
        self.response = self.tryGet(url)
        self.html_soup = BeautifulSoup(self.response.text, "html.parser")
        return self.response.status_code

    def saveFile(self, url, savepath):
        self.archiver.file(savepath).write(self.tryGet(url).content)
        return self.response.status_code

    def executeJS(self, jspath):
        ret = self.archiver.execute("phantomjs --ssl-protocol=any " + jspath + " \"" + self.response.url + '\"')
        if ret['err']:
            pass # something went wrong
        return [i.strip() for i in ret['out'].split('\n') if i]

    def setReferer(self, ref):
        self.session.headers['Referer'] = ref

    def parseForm(self, action):
        # Return a dict of the first form found on the page
        form = self.html_soup.find("form", action = action)
        return { e.get("name", ""): e.get("value", "") or "" for e in form.find_all("input") if e.get("name", "") }

    def parseAllElements(self, *tags):
        # Return an array of all html elements that match tags (hierarchially, going up)
        tags = [[t.split(" ")[0], "" if len(t.split(" ")) == 1 else dict([tuple(t.split(" ")[1].split('='))])] for t in tags]
        hits = []
        for elem in self.html_soup.find_all(*tags[0]):
            res = elem
            for tag in tags[1:]:
                res = res.find_parent(*tag)
                if res is None: break
            if res: hits.append(elem)
        return hits

    def parseElement(self, *tags):
        # See parseAllElements, this returns just the first match
        try: return self.parseAllElements(*tags)[0]
        except: return {}
