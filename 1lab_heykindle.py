# -*- coding: utf-8 -*-
#Basil
#Basil.20151106,23:56.try git command

import logging
import bs4
import urllib2
import urllib 
import time
import smtplib
import email
import base64
import sys
import os
import json
import subprocess
import threading

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from StringIO import StringIO
from email.generator import Generator
from email.MIMEBase import MIMEBase
from email import encoders
import mimetypes

import config

global_openids = {}

def __init():
    logging.basicConfig(level=logging.DEBUG,
        format='%(asctime)s %(process)d %(thread)d %(funcName)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
        datefmt='%a, %d %b %Y %H:%M:%S',
        filename='./log/main_kindle.log.txt',
        filemode='aw+')

class KindleMate(object):
    def __init__(self):
        super(KindleMate, self).__init__()
        self._ids = []
        self._ids_doable = [] #multiple元组列表, 分别是: 公众号, 订阅mail, url, title, 文章内容
        self._ua = 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:35.0) Gecko/20100101 Firefox/35.0'
        self._users = []
        self._useropens = {}
        self._global_done_open_article = {}
        self._global_opens = {}
        self._mfrom = 'heykindle@herecake.cc'

    def recordOpenid(self, items=None):
        #公众号入库
        if items == None: 
            for user in config.users:
                if config.useropens.has_key(user):
                    self._users.append(user)
                    self._useropens[user] = {}
                    for info in config.useropens[user]:
                        self._useropens[user][info] = 1
        else:
            pass

    def _is_new_article(self,openid,title):
        logging.debug('in _is_new_article')
        if not os.path.isfile('./html/'+title+'.html'):
            return True 
        flag = False
        for item in self._global_done_open_article[openid]:
            logging.debug('wtf?')
            if title == item['title']:
                flag = True
                break
        return flag

    def _save_openid_cache(self,openid,weixin_openid):
        try:
            import redis
            myredis = redis.StrictRedis(host='127.0.0.1',port=6789,db=1)
            myredis[openid] = weixin_openid
        except Exception,e:
            logging.error(str(e))

    def _lab_wrap(self,openid,to_del_openid):
        try:
            #Basil.不需要redis存储对应的id了
            #import redis
            #myredis = redis.StrictRedis(host='127.0.0.1',port=6789,db=1)
            #weixin_openid = myredis[openid]
            weixin_openid = ''
            self._lab_handle_result(openid,weixin_openid,to_del_openid)
            return True
            #else:
            #    return False
        except Exception,e:
            logging.error(str(e))

    def _get_cookie(self,root,pos):
        logging.debug('type of root = %s' % type(root))
        cookies = root['cookies']
        mycookies = ''
        for key,value in cookies[pos].items():
            mycookies += '%s=%s;' % (key,value)
        return mycookies

    def _lab_handle_result(self,openid,weixin_openid,to_del_openid):
        flag = True
        try:
            timeout = 45
            logging.info('now in _lab_handle_result')
            cmd = 'export LD_LIBRARY_PATH=/home/fun/iojs_bin/iojs-v3.0.0-linux-x64/lib:$LD_LIBRARY_PATH;export PATH=/home/fun/iojs_bin/iojs-v3.0.0-linux-x64/bin:$HOME/bin:/usr/bin:$PATH;'
            #cmd += 'iojs /home/fun/soft/xieran3/cli.js %s 1 -t %d' % (weixin_openid,timeout)
            cmd += 'node /home/fun/phantomjs/src/cli.js %s 1' % (openid)
            logging.debug('before iojs cmd = %s' % (cmd))
            pfile = os.popen(cmd)
            logging.debug('after iojs cmd = %s' % (cmd))
            results = pfile.read()
            pfile.close()
            #接下来就只是处理json而已了
            if len(results) == 0:
                logging.error('iojs parse page timeout, openid = %s' % (openid))
                to_del_openid.append(openid)
                flag = False
                return flag
            root = json.loads(results)
            logging.debug('before get cookies')
            logging.debug('after json loads')
            item_count = len(root['items'])
            #self._save_openid_cache(openid,weixin_openid)
            #we only take 3 first articles
            if item_count > 3:
                item_count = 3
            for i in range(0,item_count):
                title = root['items'][i]['title'].encode('utf-8')
                logging.debug('after title encode')
                url = root['items'][i]['url']
                mycookie = self._get_cookie(root,i)
                if not self._is_new_article(openid,title):
                    #如果内存没有这篇文章，但是本地有，说明是以前的文章了
                    logging.info('%s not new article for %s' % (title,openid))
                else:
                    logging.debug('in json loop else')
                    onearticle = {}
                    onearticle['title'] = title
                    onearticle['link'] = url
                    onearticle['cookie'] = mycookie
                    #Basil onearticle['referer'] = 'http://weixin.sogou.com/gzh?openid=' + weixin_openid
                    logging.debug('i dont know')
                    self._global_done_open_article[openid].append(onearticle)
                    logging.debug('after append in loop else')
            logging.debug('after json loop')
            if len(self._global_done_open_article[openid]) == 0:
                to_del_openid.append(openid)
                flag = False
            logging.info('now out of _lab_handle_result')
            return flag
        except Exception,e:
            logging.error("_lab_handle_result error, weixin_openid = %s, error = %s" % (weixin_openid,str(e)))
            flag = False
            return flag

    def __test(self,data,name):
        tfile = open(name,'aw')
        tfile.write(data)
        tfile.close()
        print 'test!!!!!!!!!!!!!! bye!'
        sys.exit(0)

    def _cookieagent(self):
        try:
            agent_cookie = urllib2.urlopen('http://weixin.sougou.com')
            cookies = agent_cookie.info().getheader('Set-Cookie')
            agent_cookie.close()
            return cookies
        except:
            return None

    def sogou(self):
        #搜狗搜索
        starttime = time.time()
        to_del_openid = []
        for user in self._users:
            item = self._useropens[user]
            for openid in item:
                #如果在这次程序生命周期，该公众号已经处理过，那么就不需要再处理了，只需要等着后面发送邮件即可
                if self._global_done_open_article.has_key(openid):
                    print 'openid aleady did, continue'
                    logging.debug('%s for %s aleady did, continue' % (openid,user))
                    continue
                try:
                    #time.sleep(30) #60
                    if time.time() - starttime > 900:
                        logging.info('process sleep for long seconds')
                        time.sleep(500)
                        starttime = time.time()
                    self._global_done_open_article[openid] = []
                    logging.info('%s tring to _lab_wrap' % (user))
                    if self._lab_wrap(openid,to_del_openid):
                        continue
                    print 'now dealing with user:%s openid:%s' % (user,openid)
                    logging.info('now dealing with user:%s openid:%s' % (user,openid))
                    sourl = 'http://weixin.sogou.com/weixin?type=1&fr=sgsearch&ie=utf8&query=' + openid
                    headers = {}
                    headers['User-Agent'] = self._ua #'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36'
                    request = urllib2.Request(sourl, headers=headers)
                    logging.debug('fetching url :%s' % (sourl))
                    agent = urllib2.urlopen(request, timeout=60)
                    logging.debug('urlopen done')
                    data = agent.read()
                    agent.close()
                    logging.debug('after fetching url :%s' % (sourl))
                    root = bs4.BeautifulSoup(data, from_encoding='utf-8')
                    #self.__test(data,"test.html")
                    #下面获取第一个公众号
                    item1 = root.find(attrs={"class":"wx-rb bg-blue wx-rb_v1 _item"})
                    if item1 == None:
                        print 'openid %s wx-rb bg-blue wx-rb_v1 _item not found' % (openid)
                        logging.error('openid %s wx-rb bg-blue wx-rb_v1 _item not found' % (openid))
                        #self.__test(data,"test.html")
                        to_del_openid.append(openid)
                        continue
                    #获得公众号openid
                    weixin_openid = item1['href']
                    idpos = weixin_openid.find('/gzh?openid=')
                    if idpos >= 0:
                        self._lab_handle_result(openid,weixin_openid[idpos+12:],to_del_openid)
                        continue 
                    #如果找不到，就走回原来的路径
                    list_latest_article = item1.findAll(attrs={'class':'sp-txt'})
                    if len(list_latest_article) != 0:
                        article = list_latest_article[-1]
                        if article != None and article != '':
                            logging.debug('%s getting link' % (openid))
                            print article.a
                            link = article.a['href']
                            if link == None:
                                logging.error('openid:%s no link found' % (openid))
                                to_del_openid.append(openid)
                                continue
                            logging.debug('%s getting title' % (openid) )
                            title = None
                            if title != None:
                                title = title.encode('utf-8')
                                logging.debug('openid:%s title got!' % (openid) )
                            else:
                                #test
                                title = ''
                                for item in article.a.contents:
                                    item = item.encode('utf-8')
                                    print item
                                    if 'em' in item:
                                        pos1 = item.find('-->')
                                        if pos1 >= 0:
                                            item = item[pos1+3:]
                                            pos2 = item.find('<!')
                                            if pos2 > 0:
                                                item = item[:pos2]
                                    title += item
                                print title
                                logging.debug('openid:%s title got!')
                            #test
                            #title = article.a.contents[0].encode('utf-8')
                            if not self._is_new_article(openid,title):
                                #如果内存没有这篇文章，但是本地有，说明是以前的文章了
                                print 'openid %s no new article found' % (openid)
                                logging.info('%s no new article found' % (openid))
                                to_del_openid.append(openid)
                            else:
                                onearticle = {}
                                onearticle['title'] = title
                                onearticle['link'] = link
                                self._global_done_open_article[openid].append(onearticle)
                    else:
                        st = 'no latest articles found for %s' % (openid)
                        print st
                        logging.error(st)
                        to_del_openid.append(openid)
                        continue
                except Exception,e:
                    print str(e)
                    logging.error(str(e))
                    time.sleep(10)
            for todelopen in to_del_openid:
                print todelopen
                if self._global_done_open_article.has_key(todelopen):
                    logging.info('deleting openid : %s' % (todelopen))
                    del self._global_done_open_article[todelopen]

    def __writeNewHtmlToFile(self,data,title):
        path = './html/' + title + '.html'
        logging.debug('before is file %s' % (title))
        if os.path.isfile(path):
            print 'bye t'
            logging.debug('after is file %s' % (title))
            return path
        logging.debug('before open file %s' % (title))
        mfile = open(path, "aw+")
        logging.debug('after open file %s' % (title))
        mfile.write(data)
        mfile.close()
        print 'bye ttt'
        return path

    def __getBase64Img(self,url):
        try:
            tppos = url.find('&tp=webp')
            if tppos >= 0:
                #不要tp参数，否则可能导致获取webp格式而kindle不支持
                url = url.replace('&tp=webp','') 
            srcprefix = 'data:image/jpg;base64,'
            headers = {}
            headers['User-Agent'] = self._ua #'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36'
            request = urllib2.Request(url,headers=headers)
            rawdata = urllib2.urlopen(request).read()
            base64data = base64.b64encode(rawdata)
            return srcprefix + base64data
        except Exception,e:
            print str(e)
            logging.error(e)
            return None

    def _fetchSiteRoutine(self,request,myagent):
        try:
            agent = urllib2.urlopen(request,timeout=45)
            myagent.append(agent)
        except Exception, e:
            logging.error('_fetchSiteRoutine error, reason=%s' % str(e))

    def fetchWebsites(self):
        #获取文章
        for user in self._users:
            #拿到每个user的openid
            for openid in self._useropens[user]: 
                logging.info('fetch website of openid:%s' % (openid))
                if not self._global_done_open_article.has_key(openid):
                    logging.debug('no need to fetch website of openid:%s' % (openid))
                    continue
                for item in self._global_done_open_article[openid]:
                    try:
                        time.sleep(5)
                        title = item['title']
                        url = 'http://weixin.sogou.com' + item['link'] #Basil.sogou修改了返回链接，变成相对路径了
                        cookie = item['cookie']
                        #referer = item['referer']
                        print 'cookie=', cookie
                        #print 'referer=', referer
                        logging.debug('fetching url = %s' % url)
                        headers = {}
                        headers['User-Agent'] = self._ua#'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/43.0.2357.81 Safari/537.36'
                        if cookie != None:
                            headers['Cookie'] = cookie
                        #if referer != None:
                        #    headers['Referer'] = referer
                        request = urllib2.Request(url,headers=headers) 
                        agent = urllib2.urlopen(request,timeout=45)

                        #sometimes i need threading
                        #myagent = []
                        #myroutine = threading.Thread(target=self._fetchSiteRoutine,args=(request, myagent))
                        #myroutine.start()
                        #myroutine.join(timeout=45)
                        #agent = myagent[0]

                        data = agent.read()
                        agent.close()
                        #self.__test(data,'mytest.test')
                        root = bs4.BeautifulSoup(data)
                        maintitle = root.find(attrs={"class":"rich_media_title"})
                        if maintitle != None:
                            contents = maintitle.get_text().encode('utf-8')
                            xixi = root.findAll(name='script',attrs={'type':'text/html'})
                            for xitem in xixi:
                                xitem.extract()
                            scripts = root.findAll(name='script')
                            for sitem in scripts:
                                sitem.extract()
                            imgs = root.findAll(name='img')
                            for img in imgs:
                                if img.has_attr('data-src'):
                                    base64data = self.__getBase64Img(img['data-src'])
                                    if base64data != None:
                                        img['src'] = base64data
                            newdata = str(root)
                            logging.debug('before write to local file, title = %s' % (title))
                            path = self.__writeNewHtmlToFile(newdata,title)
                            logging.debug('after write to local file, title = %s' % (title))
                            item['path'] = path
                            print 'adding path %s for openid: %s' % (path,openid)
                        else:
                            print '%s error' % (openid)
                            logging.error('%s title not found in rich_media_title' % (openid))
                        time.sleep(3)
                    except Exception,e:
                        print str(e)
                        logging.error(str(e))
                        continue

    def parseWebsites(self):
        #解析文章
        pass

    def __getFilenameViaPath(self,path):
        pos = path.find('./html/')
        return path[7:]
        pass

    def _generateIndexHtml(self, useropenids):
        todaytime = time.localtime()
        title = 'HeyKindle每日投递_%s-%s-%s' % (todaytime.tm_year,todaytime.tm_mon,todaytime.tm_mday)
        filename = title + '.mobi'
        html = '<html><head><meta charset=\"utf-8\" /><title>%s</title></head>' % (title)
        html += '<body><p style=\"font-style:italic\">'
        import const
        html += const.poet
        html += '</p><br />'
        html += '<p style=\"font-weight:bold;font-size:17px\">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Hey kindle，向阅读说声好。</p>'
        html += '<h1>目录</h1><br />'
        os.system("rm ./books/*")
        articlecount = 0
        for openid in useropenids:
            print 'in _generateIndexHtml, openid = %s' % (openid)
            if not self._global_done_open_article.has_key(openid):
                logging.info('dont deal with openid: %s because it is deleted' % (openid))
                print 'not deal with opendi:%s' % (openid)
                continue
            for item in self._global_done_open_article[openid]:
                try:
                    print 'cp path = %s' % (item['path'])
                    cmd = "cp \"%s\" ./books/ " % (item['path'])
                    ret = os.system(cmd)
                    if ret == 0:
                        html += '<a href=\"%s.html\">%s</a><br /><br />' % (item['title'],item['title'])
                        articlecount += 1
                except Exception,e:
                    logging.error('packMailAtach error = %s' % str(e))
                    continue
        if articlecount == 0:
            return None
        html += '</body></html>'
        htmlfile = open('./books/index.html','aw+')
        htmlfile.write(html)
        htmlfile.close()
        return filename

    def _generateMobiBook(self,filename):
        cmd = 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/fun/cali/calibre/lib;/home/fun/cali/calibre/bin/ebook-convert ./books/index.html %s --authors HeyKindle' % (filename)
        ret = os.system(cmd)
        os.system('rm ./books/*')
        if ret == 0:
            return True
        else:
            return False
    
    def packMailAtach(self):
        #打包组装邮件附件
        for user in self._users:
            filename = self._generateIndexHtml(self._useropens[user])
            if filename == None:
                logging.info('no deliver  for user %s today' % (user))
                continue
            if not self._generateMobiBook(filename):
                continue
            agent = smtplib.SMTP()
            agent.connect('127.0.0.1', 25)
            print 'filename = %s' % (filename)
            try:
                msg = MIMEMultipart()
                data = open(filename, 'r').read()#.decode('utf-8')

                att1 = MIMEText(data,'plain','utf-8')
                #filename = self.__getFilenameViaPath(self._global_done_open_article[openid]['path'])
                realname = filename
                filename = '=?utf8?B?' + base64.b64encode(filename) + '?='

                att1['Content-Disposition'] = 'attachment; filename="%s"' % (filename)  #% (self._ids_doable[i][5])
                att1['Content-Type'] = 'application/octet-stream'
                msg.attach(att1)

                mtos = user
                msg['To'] = mtos 
                msg['From'] = self._mfrom  
                msg['Subject'] = 'Convert' #self._ids_doable[0][3].encode('utf-8')

                fp = StringIO()
                gen = Generator(fp, mangle_from_=False)
                gen.flatten(msg)
                msg = fp.getvalue()

                print 'send to ', mtos
                logging.info('begin to send to %s' % (user))
                agent.sendmail(self._mfrom, mtos, msg)
                logging.info('send to %s done!' % (user) )
                os.system('rm ./%s' % (realname))
                time.sleep(5)
            except Exception,e:
                print str(e)
                logging.error(str(e))
                os.system('rm ./%s' % (realname))
                continue
            agent.quit()
            time.sleep(60)

    def sendMail(self):
        pass

def main():
    __init()
    logging.info('i am started! world is good, use python!')
    km = KindleMate()
    km.recordOpenid()
    km.sogou()
    km.fetchWebsites()
    km.packMailAtach()
    logging.info('bye! pythoner is hot!')

def main1():
    timeout = 10
    weixin_openid = 'oIWsFt7wtzJx0HP4w_znRUodtmus'
    cmd = 'export LD_LIBRARY_PATH=/home/fun/iojs_bin/iojs-v3.0.0-linux-x64/lib:$LD_LIBRARY_PATH;export PATH=/home/fun/iojs_bin/iojs-v3.0.0-linux-x64/bin:$HOME/bin:/usr/bin:$PATH;'
    cmd += 'iojs /home/fun/soft/xieran3/cli.js %s 1 -t %d' % (weixin_openid,timeout)
    pfile = os.popen(cmd)
    results = pfile.read()
    pfile.close()
    root = json.loads(results)
    cookies = root['cookies']['object']
    mycookies = ''
    for item in cookies:
        key = item['key']
        value = item['value']
        mycookies += '%s=%s;' % (key,value)
    url = ''
    for oneitem in root['items']:
        url = oneitem['url']
        break
    url = 'http://weixin.sogou.com' + url
    headers = {}
    headers['User-Agent'] =  'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:35.0) Gecko/20100101 Firefox/35.0'
    print mycookies
    headers['Cookie'] = mycookies
    headers['Referer'] = 'http://weixin.sogou.com/gzh?openid=oIWsFt7wtzJx0HP4w_znRUodtmus'
    request = urllib2.Request(url=url,headers=headers)
    agent = urllib2.urlopen(request)
    print agent.code
    data = agent.read()
    print data

if __name__ == '__main__':
    main()
