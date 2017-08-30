import os
from subprocess import Popen, PIPE
from numpy import average, std as stddev


class Archiver(object):

    def __init__(self):
        self.logname = "log"

    def exists(self, path):
        pass # TODO

    def folder(self, path):
        if path:
            if path[-1] != '/': path += "/"
            os.makedirs(os.path.dirname(path), exist_ok = True)
            return path
        else:
            return None

    def file(self, path, params = 'wb'):
        self.folder('/'.join(path.split('/')[:-1]) + '/')
        return open(path, params)

    def execute(self, command):
        p = Popen(command, shell = True, stdout= PIPE, stderr = PIPE)
        out, err = p.communicate()
        return {'out': out.decode(), 'err': err.decode()}

    def log(self, string):
        self.file(self.logname, 'a').write(string + '\n')

    def copy(self, src, dst):
        return self.execute("cp -r " + src + " " + dst)

    def move(self, src, dst):
        ret = self.copy(src, dst)
        if not ret['err']:
            return self.remove(src)
        return ret

    def remove(self, files):
        return self.execute("rm -r " + files)

    def zipToAnimation(self, sourcepath, destpath, filename, framedata):
        destpath = self.folder(destpath)
        workpath = "temp/" + filename
        self.execute("unzip -o " + sourcepath + " -d " + workpath)

        if stddev(framedata) < 1.0:
            # assumed stable framerate
            fr = 1 / round(average(framedata)) * 1000
            self.execute("ffmpeg -framerate %d -i %s/%%6d.jpg -c:v copy %s.mkv" % (fr, workpath, destpath + filename))
            
        else:
            # probably needs variable framerate
            print("\n stddev %.3f, %d frames:\n" % (stddev(framedata), len(framedata)), framedata)
            cmd = "convert "
            for i, d in enumerate(framedata):
                cmd += "-delay %d %s/%06d.jpg " % (d / 10, workpath, i)
            cmd += destpath + filename + ".gif"
            self.execute(cmd) # we convert to gif and copy the zip too, because gif is trash
            self.execute("cp " + sourcepath + " " + destpath + filename + ".zip")
