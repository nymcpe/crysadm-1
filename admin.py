__author__ = 'powergx'
from flask import request, Response, render_template, session, url_for, redirect
from crysadm import app, r_session
from auth import requires_admin, requires_auth
import json
from util import hash_password
import uuid
import re
import random


@app.route('/admin/user')
@requires_admin
def admin_user():
    users = list()

    for username in sorted(r_session.smembers('users')):
        b_user = r_session.get('user:%s' % username.decode('utf-8'))
        if b_user is None:
            continue
        users.append(json.loads(b_user.decode('utf-8')))

    return render_template('admin_user.html', users=users)


@app.route('/admin/message')
@requires_admin
def admin_message():
    users = list()

    for username in sorted(r_session.smembers('users')):
        b_user = r_session.get('user:%s' % username.decode('utf-8'))
        if b_user is None:
            continue
        users.append(json.loads(b_user.decode('utf-8')))

    return render_template('admin_message.html', users=users,inv_codes=r_session.smembers('invitation_codes'))


@app.route('/admin/invitation')
@requires_admin
def admin_invitation():
    return render_template('admin_invitation.html', inv_codes=r_session.smembers('invitation_codes'))


@app.route('/generate/inv_code', methods=['POST'])
@requires_admin
def generate_inv_code():
    _chars = "0123456789ABCDEF"
    r_session.smembers('invitation_codes')

    for i in range(0, 20 - r_session.scard('invitation_codes')):
        r_session.sadd('invitation_codes',''.join(random.sample(_chars, 10)))

    return redirect(url_for('admin_invitation'))


@app.route('/admin/login_as/<username>', methods=['POST'])
@requires_admin
def generate_login_as(username):
    user_info = r_session.get('%s:%s' % ('user', username))

    user = json.loads(user_info.decode('utf-8'))

    session['admin_user_info'] = session.get('user_info')
    session['user_info'] = user

    return redirect(url_for('dashboard'))


@app.route('/admin_user/<username>')
@requires_admin
def admin_user_management(username):
    err_msg = None
    if session.get('error_message') is not None:
        err_msg = session.get('error_message')
        session['error_message'] = None

    user = json.loads(r_session.get('user:%s' % username).decode('utf-8'))

    return render_template('user_management.html', user=user, err_msg=err_msg)


@app.route('/admin/change_password/<username>', methods=['POST'])
@requires_admin
def admin_change_password(username):
    n_password = request.values.get('new_password')

    if len(n_password) < 8:
        session['error_message'] = '密码必须8位以上.'
        return redirect(url_for(endpoint='admin_user', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['password'] = hash_password(n_password)
    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user', username=username))


@app.route('/admin/change_property/<field>/<value>/<username>', methods=['POST'])
@requires_admin
def admin_change_property(field, value, username):
    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    if field == 'is_admin':
        user_info['is_admin'] = True if value == '1' else False
    elif field == 'active':
        user_info['active'] = True if value == '1' else False
    elif field == 'auto_collect':
        user_info['auto_collect'] = True if value == '1' else False


    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user', username=username))


@app.route('/admin/change_user_info/<username>', methods=['POST'])
@requires_admin
def admin_change_user_info(username):
    max_account_no = request.values.get('max_account_no')

    r = r"^[1-9]\d*$"

    if re.match(r, max_account_no) is None:
        session['error_message'] = '迅雷账号限制必须为整数.'
        return redirect(url_for(endpoint='admin_user', username=username))

    if not 0 < int(max_account_no) < 21:
        session['error_message'] = '迅雷账号限制必须为 1~20.'
        return redirect(url_for(endpoint='admin_user', username=username))

    user_key = '%s:%s' % ('user', username)
    user_info = json.loads(r_session.get(user_key).decode('utf-8'))

    user_info['max_account_no'] = int(max_account_no)

    r_session.set(user_key, json.dumps(user_info))

    return redirect(url_for(endpoint='admin_user', username=username))


@app.route('/admin/del_user/<username>', methods=['GET'])
@requires_admin
def admin_del_user(username):
    if r_session.get('%s:%s' % ('user', username)) is None:
        session['error_message'] = '账号不存在'
        return redirect(url_for(endpoint='admin_user', username=username))

    # do del user
    r_session.delete('%s:%s' % ('user', username))
    r_session.srem('users', username)
    for b_account_id in r_session.smembers('accounts:' + username):
        account_id = b_account_id.decode('utf-8')
        r_session.delete('account:%s:%s' % (username, account_id))
        r_session.delete('account:%s:%s:data' % (username, account_id))
    r_session.delete('accounts:' + username)

    for key in r_session.keys('user_data:%s:*' % username):
        r_session.delete(key.decode('utf-8'))

    return redirect(url_for('admin_user'))


@app.route('/none_user')
@requires_admin
def none_user():
    none_xlAcct = list()
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            none_xlAcct.append(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)

    return json.dumps(dict(none_xlAcct=none_xlAcct, none_active_xlAcct=none_active_xlAcct))


@app.route('/del_none_user')
@requires_admin
def del_none_user():
    none_active_xlAcct = list()
    for b_user in r_session.smembers('users'):
        username = b_user.decode('utf-8')

        if r_session.smembers('accounts:' + username) is None or len(r_session.smembers('accounts:' + username)) == 0:
            admin_del_user(username)
        has_active_account = False
        for b_xl_account in r_session.smembers('accounts:' + username):
            xl_account = b_xl_account.decode('utf-8')
            account = json.loads(r_session.get('account:%s:%s' % (username, xl_account)).decode('utf-8'))
            if account.get('active'):
                has_active_account = True
                break
        if not has_active_account:
            none_active_xlAcct.append(username)

    return json.dumps(dict( none_active_xlAcct=none_active_xlAcct))


@app.route('/admin/message/send', methods=['POST'])
@requires_admin
def admin_message_send():
    to = request.values.get('to')
    subject = request.values.get('subject')
    summary = request.values.get('summary')
    content = request.values.get('content')

    if subject == '':
        session['error_message'] = '标题为必填。'
        return redirect(url_for('admin_message'))

    if to == '':
        session['error_message'] = '收件方必填。'
        return redirect(url_for('admin_message'))

    if summary == '':
        session['error_message'] = '简介必填'
        return redirect(url_for('admin_message'))



    return '功能已关闭'
    i =0
    for b_username in r_session.smembers('users'):
        i += 1
        if i >10000:
            break
        send_msg(b_username.decode('utf-8'), '新域名通知 crysadm.com！', '最好看的矿场监工有新的访问姿势:crysadm.com           <br /> <br />'
                                                  '''<table class="table table-bordered">
                                                      <tbody>
                                                      <tr>

                                                        <td>国内用户</td>
                                 <td><a href="https://crysadm.com">crysadm.com</a></td>
                                                                          </tr>
                                                                          <tr>
                                                                              <td>海外用户</td>
                                                                              <td><a href="https://os.crysadm.com">os.crysadm.com</a></td>
                                                                          </tr>
                                                                          </tbody>
                                                                      </table>
                                                                      ''', expire=3600*24)
    return '发送成功'
