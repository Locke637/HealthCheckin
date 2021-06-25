# -*- coding: utf-8 -*-
import requests, json, re
import time, datetime, os
import getpass

# 环境变量
# 统一认证学号
username = os.environ["USERNAME"]
# username = ''
# 统一认证密码
password = os.environ["PASSWORD"]
# password = ''
# DingTalk的sckey和加签信息
sckey = os.environ["PUSH_KEY"]
secret = os.environ["PUSH_SECRET"]

def send_message(title='无效', text=''):
    if text == '':
        requests.post('https://api.animo.top/dingtalk/send?token=' + sckey + '&secret=' + secret + '&title=健康打卡通知&text=健康打卡通知 \n\n' + title)
    else:
        requests.post('https://api.animo.top/dingtalk/send?card=1&token=' + sckey + '&secret=' + secret + '&title=' + title + '&text=' + text)
    return

class HitCarder(object):
    """Hit carder class
    Attributes:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
        login_url: (str) 登录url
        base_url: (str) 打卡首页url
        save_url: (str) 提交打卡url
        self.headers: (dir) 请求头
        sess: (requests.Session) 统一的session
    """

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.login_url = "https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fhealthreport.zju.edu.cn%2Fa_zju%2Fapi%2Fsso%2Findex%3Fredirect%3Dhttps%253A%252F%252Fhealthreport.zju.edu.cn%252Fncov%252Fwap%252Fdefault%252Findex"
        self.base_url = "https://healthreport.zju.edu.cn/ncov/wap/default/index"
        self.save_url = "https://healthreport.zju.edu.cn/ncov/wap/default/save"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
        }
        self.sess = requests.Session()

    def login(self):
        """Login to ZJU platform."""
        res = self.sess.get(self.login_url, headers=self.headers)
        execution = re.search('name="execution" value="(.*?)"', res.text).group(1)
        res = self.sess.get(url='https://zjuam.zju.edu.cn/cas/v2/getPubKey', headers=self.headers).json()
        n, e = res['modulus'], res['exponent']
        encrypt_password = self._rsa_encrypt(self.password, e, n)

        data = {
            'username': self.username,
            'password': encrypt_password,
            'execution': execution,
            '_eventId': 'submit'
        }
        res = self.sess.post(url=self.login_url, data=data, headers=self.headers)

        # check if login successfully
        if '统一身份认证' in res.content.decode():
            raise LoginError('登录失败，请核实账号密码重新登录')
        return self.sess

    def post(self):
        """Post the hit card info."""
        res = self.sess.post(self.save_url, data=self.info, headers=self.headers)
        return json.loads(res.text)

    def get_date(self):
        """Get current date."""
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def get_info(self, html=None):
        """Get hit card info, which is the old info with updated new time."""
        if not html:
            res = self.sess.get(self.base_url, headers=self.headers)
            html = res.content.decode()

        try:
            old_infos = re.findall(r'oldInfo: ({[^\n]+})', html)
            if len(old_infos) != 0:
                old_info = json.loads(old_infos[0])
            else:
                raise RegexMatchError("未发现缓存信息，请先至少手动成功打卡一次再运行脚本")

            new_info_tmp = json.loads(re.findall(r'def = ({[^\n]+})', html)[0])
            new_id = new_info_tmp['id']
            name = re.findall(r'realname: "([^\"]+)",', html)[0]
            number = re.findall(r"number: '([^\']+)',", html)[0]
        except IndexError as err:
            raise RegexMatchError('Relative info not found in html with regex: ' + str(err))
        except json.decoder.JSONDecodeError as err:
            raise DecodeError('JSON decode error: ' + str(err))

        new_info = old_info.copy()
        new_info['id'] = new_id
        new_info['name'] = name
        new_info['number'] = number
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        # todo
        # new_info['address'] = '浙江省杭州市西湖区余杭塘路866号浙江大学紫金港校区'   # 如: 'xx省xx市xx区xx街道xx小区'
        # new_info['area'] = '浙江省 杭州市 西湖区'     # 如: '浙江省 杭州市 西湖区'  记得中间用空格隔开, 省市区/县名称可以参考 打卡页面->基本信息->家庭所在地 中对应的省市区/县名
        # new_info['province'] = new_info['area'].split(' ')[0]   # 省名
        # new_info['city'] = new_info['area'].split(' ')[1]       # 市名
        # form change
        new_info['jrdqtlqk[]'] = 0
        new_info['jrdqjcqk[]'] = 0
        new_info['sfsqhzjkk'] = 1  # 是否申领杭州健康码
        new_info['sqhzjkkys'] = 1  # 杭州健康吗颜色，1:绿色 2:红色 3:黄色
        new_info['sfqrxxss'] = 1  # 是否确认信息属实
        new_info['sfymqjczrj'] = 0  # 是否密切接触家人入境
        new_info['jcqzrq'] = ""
        new_info['gwszdd'] = ""
        new_info['szgjcs'] = ""
        self.info = new_info
        return new_info

    def _rsa_encrypt(self, password_str, e_str, M_str):
        password_bytes = bytes(password_str, 'ascii')
        password_int = int.from_bytes(password_bytes, 'big')
        e_int = int(e_str, 16)
        M_int = int(M_str, 16)
        result_int = pow(password_int, e_int, M_int)
        return hex(result_int)[2:].rjust(128, '0')


# Exceptions 
class LoginError(Exception):
    """Login Exception"""
    pass


class RegexMatchError(Exception):
    """Regex Matching Exception"""
    pass


class DecodeError(Exception):
    """JSON Decode Exception"""
    pass


def main(username, password):
    """Hit card process
    Arguments:
        username: (str) 浙大统一认证平台用户名（一般为学号）
        password: (str) 浙大统一认证平台密码
    """
    start_time = ("\n[Time] %s" %datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("\n[Time] %s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚌 打卡任务启动")

    hit_carder = HitCarder(username, password)


    print('登录到浙大统一身份认证平台...')
    try:
        hit_carder.login()
        print('已登录到浙大统一身份认证平台')
    except Exception as err:
        print(str(err))
        return

    print('正在获取个人信息...')
    try:
        hit_carder.get_info()
        personal_info = ('%s %s同学, 你好~' % (hit_carder.info['number'], hit_carder.info['name']))
        # print('%s %s同学, 你好~' % (hit_carder.info['number'], hit_carder.info['name']))
    except Exception as err:
        print('获取信息失败，请手动打卡，更多信息: ' + str(err))
        send_message(title='获取信息失败，请手动打卡，更多信息:', text=str(err))
        return

    print('正在为您打卡...')
    try:
        res = hit_carder.post()
        if str(res['e']) == '0':
            print('已为您打卡成功！')
            send_message(title='打卡🎈成功!', text=start_time+'\n\n'+personal_info+'\n\n From HealthCheck.')
        else:
            print(res['m'])
            send_message(title=res['m']+'[Check here](https://healthreport.zju.edu.cn/ncov/wap/default/index)')
    except Exception as err:
        print('数据提交失败 ' + str(err))
        send_message(title='数据提交失败' + str(err))
        return


if __name__ == "__main__":
    try:
        main(username, password)
    except (KeyboardInterrupt, SystemExit):
        pass
