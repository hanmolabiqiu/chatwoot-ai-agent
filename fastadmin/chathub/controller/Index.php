<?php
namespace addons\chathub\controller;

use addons\chathub\model\ChathubTenant;
use app\common\controller\Backend;
use think\Db;

class Index extends Backend
{
    protected $model = null;
    protected $noNeedLogin = ['register', 'landing', 'registerPage', 'login', 'doLogin', 'logout', 'changePassword', 'renew', 'payAlipay', 'payWechat', 'payNotify', 'payReturn'];
    protected $noNeedRight = ['register', 'landing', 'registerPage', 'login', 'doLogin', 'logout', 'changePassword', 'renew', 'payAlipay', 'payWechat', 'payNotify', 'payReturn'];

    public function _initialize()
    {
        $publicActions = ['login', 'doLogin', 'register', 'landing', 'registerPage', 'logout', 'payNotify', 'payReturn'];
        if (in_array($this->request->action(), $publicActions)) {
            $this->model = new ChathubTenant();
            return;
        }
        $userActions = ['my', 'channellist', 'channelauth', 'channelcallback', 'reprovision'];
        if (session('chathub_user_id') && in_array($this->request->action(), $userActions)) {
            $this->model = new ChathubTenant();
            return;
        }
        parent::_initialize();
        $this->model = new ChathubTenant();
    }

    private function render($content)
    {
        header('Content-Type: text/html; charset=utf-8');
        echo $content;
        exit;
    }

    private function layout($title, $body)
    {
        return '<!DOCTYPE html><html><head><meta charset="utf-8"><title>' . $title . '</title>
<link href="/assets/css/backend.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@5.15.4/css/all.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
<style>
body{background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:20px}
.container{max-width:1200px;margin:0 auto}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);margin-bottom:20px;overflow:hidden}
.card-header{padding:16px 24px;border-bottom:1px solid #f0f0f0;display:flex;justify-content:space-between;align-items:center}
.card-header h2{margin:0;font-size:18px;font-weight:600;color:#1a1a1a}
.card-body{padding:24px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:8px;font-size:14px;font-weight:500;border:none;cursor:pointer;text-decoration:none;transition:all .2s}
.btn-primary{background:#4f46e5;color:#fff}
.btn-primary:hover{background:#4338ca}
.btn-secondary{background:#fff;color:#374151;border:1px solid #d1d5db}
.btn-secondary:hover{background:#f9fafb}
.btn-danger{background:#ef4444;color:#fff}
.btn-sm{padding:4px 10px;font-size:12px}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:14px;font-weight:500;color:#374151;margin-bottom:6px}
.form-control{width:100%;padding:8px 12px;border:1px solid #d1d5db;border-radius:6px;font-size:14px;box-sizing:border-box}
.form-control:focus{outline:none;border-color:#4f46e5;box-shadow:0 0 0 3px rgba(79,70,229,.1)}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 16px;text-align:left;border-bottom:1px solid #f0f0f0;font-size:14px}
th{background:#fafafa;font-weight:600;color:#6b7280;font-size:12px;text-transform:uppercase}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500}
.badge-success{background:#d1fae5;color:#065f46}
.badge-warning{background:#fef3c7;color:#92400e}
.badge-danger{background:#fee2e2;color:#991b1b}
.actions{display:flex;gap:8px}
.nav{display:flex;gap:8px;margin-bottom:20px}
.nav a{padding:8px 16px;border-radius:8px;text-decoration:none;font-size:14px;color:#374151;background:#fff;border:1px solid #d1d5db}
.nav a.active{background:#4f46e5;color:#fff;border-color:#4f46e5}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
.stat-card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.stat-card .number{font-size:32px;font-weight:700;color:#1a1a1a}
.stat-card .label{font-size:14px;color:#6b7280;margin-top:4px}
</style>
</head><body>
<div class="container">' . $body . '</div>
</body></html>';
    }

    public function index()
    {
        if ($this->request->isAjax()) {
            $filter = $this->request->request("filter");
            $filter = (array)json_decode($filter, true);
            $where = [];
            if (!empty($filter['status'])) $where['status'] = $filter['status'];
            if (!empty($filter['channel_type'])) $where['channel_type'] = $filter['channel_type'];
            if (!empty($filter['search'])) $where['tenant_name|domain'] = ['like', '%' . $filter['search'] . '%'];
            $list = $this->model->where($where)->order('id desc')->paginate();
            return json(["total" => $list->total(), "rows" => $list->items()]);
        }

        $html = '<div class="card"><div class="card-header">
            <h2>租户管理</h2>
            <div><a href="/pGTnXkhdmy.php/addons/chathub/index/dashboard" class="btn btn-secondary"><i class="fa fa-tachometer"></i> 控制面板</a></div>
        </div><div class="card-body">
        <table><thead><tr><th>租户</th><th>域名</th><th>邮箱</th><th>通道</th><th>席位</th><th>状态</th><th>到期时间</th><th>操作</th></tr></thead>
        <tbody id="list"></tbody></table>
        <div id="empty" style="display:none;text-align:center;padding:40px;color:#9ca3af"><i class="fa fa-inbox" style="font-size:48px;margin-bottom:16px"></i><p>暂无租户</p></div>
        <div id="pager" style="display:flex;justify-content:space-between;align-items:center;padding-top:16px;border-top:1px solid #f0f0f0;margin-top:16px">
            <span id="page-info"></span><div id="pagination"></div>
        </div>
        </div></div>';

        $html .= '<script>
        function load(p){
            p=p||1;
            $.get("/pGTnXkhdmy.php/addons/chathub/index/index",{page:p,filter:"{}"},function(r){
                if(r.rows&&r.rows.length>0){
                    var h="";
                    r.rows.forEach(function(t){
                        var sc="badge-"+(t.status=="active"?"success":t.status=="pending"?"warning":"danger");
                        h+="<tr>";
                        h+="<td><strong>"+t.tenant_name+"</strong>"+(t.agent_name?"<br><small>"+t.agent_name+"</small>":"")+"</td>";
                        h+="<td>"+t.domain+"</td>";
                        h+="<td>"+(t.email||"-")+"</td>";
                        h+="<td>"+(t.channel_type=="web_widget"?"网页组件":"API")+"</td>";
                        h+="<td>"+t.max_agents+"</td>";
                        h+="<td><span class=\"badge "+sc+"\">"+t.status_text+"</span></td>";
                        h+="<td>"+(t.expire_at||"未设置")+"</td>";
                        h+="<td><div class=\"actions\">";
                        if(t.status=="active"){
                            h+="<button onclick=\"suspend("+t.id+")\" class=\"btn btn-secondary btn-sm\"><i class=\"fa fa-pause\"></i> 暂停</button>";
                        } else if(t.status=="suspended"){
                            h+="<button onclick=\"activate("+t.id+")\" class=\"btn btn-primary btn-sm\"><i class=\"fa fa-play\"></i> 恢复</button>";
                        }
                        h+="<button onclick=\"setExpire("+t.id+")\" class=\"btn btn-secondary btn-sm\"><i class=\"fa fa-clock\"></i> 到期</button>";
                        h+="<button onclick=\"del("+t.id+")\" class=\"btn btn-danger btn-sm\"><i class=\"fa fa-trash\"></i></button>";
                        h+="</div></td></tr>";
                    });
                    $("#list").html(h);$("#empty").hide();$("table").show();$("#pager").show();
                } else {
                    $("#empty").show();$("table").hide();$("#pager").hide();
                }
            },"json");
        }
        function suspend(id){if(confirm("暂停该租户？"))$.post("/pGTnXkhdmy.php/addons/chathub/index/suspend",{ids:id},function(r){alert(r.msg);load()},"json");}
        function activate(id){if(confirm("恢复该租户？"))$.post("/pGTnXkhdmy.php/addons/chathub/index/activate",{ids:id},function(r){alert(r.msg);load()},"json");}
        function setExpire(id){
            var d=prompt("设置到期时间 (格式: 2026-12-31)");
            if(d)$.post("/pGTnXkhdmy.php/addons/chathub/index/setExpire",{ids:id,expire_at:d},function(r){alert(r.msg);load()},"json");
        }
        function del(id){if(confirm("确定删除？"))$.post("/pGTnXkhdmy.php/addons/chathub/index/del",{ids:id},function(r){alert(r.msg);load()},"json");}
        load();
        </script>';

        $this->render($this->layout('租户列表', $html));
    }

    public function add()
    {
        if ($this->request->isPost()) {
            $params = $this->request->post("row/a");
            if ($params) {
                Db::startTrans();
                try {
                    $result = $this->model->allowField(true)->save($params);
                    Db::commit();
                } catch (\Exception $e) {
                    Db::rollback();
                    $this->error($e->getMessage());
                }
                if ($result !== false) {
                    $this->success('添加成功！', '/pGTnXkhdmy.php/addons/chathub/index/index');
                }
                $this->error($this->model->getError());
            }
            $this->error('参数不能为空');
        }

        $html = '<div class="nav"><a href="/pGTnXkhdmy.php/addons/chathub/index/index">← 返回列表</a></div>
        <div class="card"><div class="card-header"><h2>添加租户</h2></div><div class="card-body">
        <form method="post">
            <div class="form-row">
                <div class="form-group"><label>租户名称 *</label><input name="row[tenant_name]" class="form-control" required></div>
                <div class="form-group"><label>域名 *</label><input name="row[domain]" class="form-control" required></div>
            </div>
            <div class="form-group"><label>管理员邮箱 *</label><input name="row[email]" type="email" class="form-control" required></div>
            <div class="form-row">
                <div class="form-group"><label>通道类型</label><select name="row[channel_type]" class="form-control"><option value="web_widget">网页组件</option><option value="api">API</option></select></div>
                <div class="form-group"><label>客服席位</label><input name="row[max_agents]" type="number" class="form-control" value="3"></div>
            </div>
            <div class="form-group"><label>Agent 名称</label><input name="row[agent_name]" class="form-control" placeholder="留空自动生成"></div>
            <div class="form-group"><label>状态</label><select name="row[status]" class="form-control"><option value="pending">待开通</option><option value="active">正常</option></select></div>
            <button type="submit" class="btn btn-primary"><i class="fa fa-save"></i> 保存</button>
        </form>
        </div></div>';

        $this->render($this->layout('添加租户', $html));
    }

    public function register()
    {
        header('Access-Control-Allow-Origin: *');
        header('Access-Control-Allow-Methods: POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type');

        if ($this->request->isOptions()) {
            exit(json_encode(['code' => 1]));
        }

        $isAjax = $this->request->isAjax() || strpos($this->request->header('content-type', ''), 'json') !== false;
        $isJson = $isAjax;

        $rawInput = file_get_contents('php://input');
        $jsonData = json_decode($rawInput, true);

        if ($jsonData) {
            $data = $jsonData;
        } else {
            $data = $this->request->post();
        }

        $companyName = trim($data['company_name'] ?? '');
        $email = trim($data['email'] ?? '');
        $domain = trim($data['domain'] ?? '');
        $plan = $data['plan'] ?? 'basic';
        $seats = (int)($data['seats'] ?? 0);
        $notes = trim($data['notes'] ?? '');

        if (!$companyName || !$email || !$domain) {
            if ($isJson) {
                header('Content-Type: application/json; charset=utf-8');
                exit(json_encode(['code' => 0, 'msg' => '请填写必填字段']));
            }
            $this->_registerResultPage(false, '请填写必填字段（公司名称、邮箱、网站域名）');
            return;
        }

        $baseSeats = 1;
        $basePrice = 50;
        $extraSeatPrice = 10;

        if ($plan === 'pro') {
            $baseSeats = 2;
            $basePrice = 60;
        } elseif ($plan === 'enterprise') {
            $baseSeats = 3;
            $basePrice = 70;
            $basePrice += $seats * $extraSeatPrice;
        }

        $totalSeats = $baseSeats + $seats;
        $expireAt = date('Y-m-d H:i:s', strtotime('+30 days'));

        $existingUser = Db::name('user')->where('email', $email)->find();
        if (!$existingUser) {
            $defaultPassword = substr(md5($email . time() . 'chathub'), 0, 10);
            $userId = Db::name('user')->insertGetId([
                'username' => $email,
                'nickname' => $companyName,
                'email' => $email,
                'password' => password_hash($defaultPassword, PASSWORD_BCRYPT),
                'salt' => '',
                'status' => 'normal',
                'jointime' => time(),
                'joinip' => $this->request->ip(),
                'createtime' => time(),
                'updatetime' => time(),
            ]);
            $createdPassword = $defaultPassword;
        } else {
            $userId = $existingUser['id'];
            $createdPassword = null;
        }

        $tenant = new ChathubTenant();
        $tenant->user_id = $userId;
        $tenant->tenant_name = $companyName;
        $tenant->domain = $domain;
        $tenant->email = $email;
        $tenant->channel_type = 'web_widget';
        $tenant->max_agents = $totalSeats;
        $tenant->status = 'provisioning';
        $tenant->expire_at = $expireAt;
        $tenant->config = json_encode(['plan' => $plan, 'price' => $basePrice, 'notes' => $notes, 'registered_at' => date('Y-m-d H:i:s'), 'initial_password' => $createdPassword]);
        $tenant->save();

        $cfg = get_addon_config('chathub');
        $provisionUrl = rtrim($cfg['provision_server_url'] ?? 'http://CoPaw:5566', '/') . '/provision';
        $payload = json_encode([
            'name' => $companyName,
            'domain' => $domain,
            'email' => $email,
            'type' => 'web_widget',
            'max_agents' => $totalSeats,
        ]);

        $idempotencyKey = 'reg-' . bin2hex(random_bytes(8));
        $ch = curl_init($provisionUrl);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-API-Key: chathub-default-key-change-me', 'Idempotency-Key: ' . $idempotencyKey],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 60,
            CURLOPT_CONNECTTIMEOUT => 10
        ]);
        $response = null;
        $curlError = '';
        $httpCode = 0;
        $attempts = 0;
        $maxAttempts = 3;

        while ($attempts < $maxAttempts) {
            $attempts++;
            $response = curl_exec($ch);
            $curlError = curl_error($ch);
            $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if (!$curlError && $httpCode == 200) {
                break;
            }

            $tenant->config = json_encode(array_merge(
                json_decode($tenant->config, true) ?: [],
                ['provision_retry' => $attempts, 'last_error' => $curlError ?: "HTTP $httpCode"]
            ));
            $tenant->save();

            if ($attempts < $maxAttempts) {
                $wait = pow(2, $attempts - 1);
                sleep($wait);
                $ch = curl_init($provisionUrl);
                curl_setopt_array($ch, [
                    CURLOPT_POST => true,
                    CURLOPT_POSTFIELDS => $payload,
                    CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-API-Key: chathub-default-key-change-me', 'Idempotency-Key: ' . $idempotencyKey],
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_TIMEOUT => 60,
                    CURLOPT_CONNECTTIMEOUT => 10
                ]);
            }
        }

        if ($curlError || $httpCode != 200) {
            $tenant->status = 'pending';
            $tenant->save();
            Db::name('chathub_log')->insert([
                'tenant_id' => $tenant->id,
                'action' => 'register',
                'detail' => "注册失败（{$attempts}次重试）: " . ($curlError ?: "HTTP $httpCode"),
                'status' => 'failed',
                'operator' => 'website',
                'createtime' => time()
            ]);
            $msg = '注册成功！正在为您开通，请稍候...';
            if ($isJson) { $this->_registerJson(1, $msg, $companyName, $plan, $basePrice, $totalSeats, '', $createdPassword, date('Y-m-d', strtotime($expireAt))); }
            $this->_registerResultPage(true, $msg, $companyName, $plan, $basePrice, $totalSeats, '', $createdPassword);
            return;
        }

        $resultData = json_decode($response, true);
        if ($resultData && isset($resultData['inbox_id'])) {
            $tenant->status = 'active';
            $tenant->provisioned_at = date('Y-m-d H:i:s');
            $tenant->inbox_id = $resultData['inbox_id'] ?? null;
            $tenant->inbox_token = $resultData['inbox_token'] ?? null;
            $tenant->embed_code = $resultData['embed_code'] ?? null;
            $tenant->agent_name = $resultData['inbox_name'] ?? null;
            $tenant->team_id = $resultData['team_id'] ?? null;
            $tenant->agent_cw_id = $resultData['agent_cw_id'] ?? null;
            $tenant->agent_cw_password = $resultData['agent_cw_password'] ?? null;
            $tenant->save();

            Db::name('chathub_log')->insert([
                'tenant_id' => $tenant->id,
                'action' => 'register',
                'detail' => "注册开通: {$companyName}, 方案: {$plan}, 席位: {$totalSeats}, 价格: ¥{$basePrice}/月" . ($attempts > 1 ? " (重试{$attempts}次后成功)" : ''),
                'status' => 'success',
                'operator' => 'website',
                'createtime' => time()
            ]);

            $msg = '注册成功！AI 客服已开通，请查收邮件获取嵌入代码。';
            if ($isJson) { $this->_registerJson(1, $msg, $companyName, $plan, $basePrice, $totalSeats, $resultData['embed_code'] ?? '', $createdPassword, date('Y-m-d', strtotime($expireAt))); }
            $this->_registerResultPage(true, $msg, $companyName, $plan, $basePrice, $totalSeats, $resultData['embed_code'] ?? '', $createdPassword);
            return;
        }

        $tenant->status = 'pending';
        $tenant->save();
        Db::name('chathub_log')->insert([
            'tenant_id' => $tenant->id,
            'action' => 'register',
            'detail' => "注册响应无效（{$attempts}次重试）",
            'status' => 'failed',
            'operator' => 'website',
            'createtime' => time()
        ]);
        $msg = '注册成功！正在为您开通，请稍候联系客服获取嵌入代码。';
        if ($isJson) { $this->_registerJson(1, $msg, $companyName, $plan, $basePrice, $totalSeats, '', $createdPassword, date('Y-m-d', strtotime($expireAt))); }
        $this->_registerResultPage(true, $msg, $companyName, $plan, $basePrice, $totalSeats, '', $createdPassword);
    }

    public function changePassword()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }
        $error = '';
        $success = '';
        if ($this->request->isPost()) {
            $old = $this->request->post('old_password');
            $new = $this->request->post('new_password');
            $confirm = $this->request->post('confirm_password');
            if (!$old || !$new || !$confirm) {
                $error = '请填写所有字段';
            } elseif ($new !== $confirm) {
                $error = '两次输入的新密码不一致';
            } elseif (strlen($new) < 6) {
                $error = '新密码至少 6 位';
            } else {
                $user = Db::name('user')->where('id', $userId)->find();
                $hashOk = !empty($user['salt']) ? (md5($old) === $user['password']) : password_verify($old, $user['password']);
                if (!$hashOk) {
                    $error = '原密码错误';
                } else {
                    Db::name('user')->where('id', $userId)->update([
                        'password' => password_hash($new, PASSWORD_BCRYPT),
                        'salt' => '',
                        'updatetime' => time(),
                    ]);
                    $success = '密码修改成功';
                }
            }
        }
        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';
        $nick = session('chathub_user_nick') ?: '';
        $msgHtml = $error ? '<div class="error">'.htmlspecialchars($error).'</div>' : '';
        if ($success) $msgHtml .= '<div class="success">'.htmlspecialchars($success).'</div>';
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>修改密码 - SITENAME</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
header{background:#0f172a;border-bottom:1px solid #1e293b;padding:18px 0}
.nav{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:20px;font-weight:700;color:#fff}
.user-info a{color:#94a3b8;margin-left:16px;text-decoration:none;font-size:13px}
.user-info a:hover{color:#fff}
.container{max-width:480px;margin:40px auto;padding:0 24px}
.card{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:36px}
h1{color:#fff;font-size:22px;margin-bottom:24px}
.form-group{margin-bottom:18px}
.form-group label{display:block;color:#cbd5e1;font-size:13px;margin-bottom:6px}
.form-control{width:100%;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#fff;font-size:15px}
.form-control:focus{outline:none;border-color:#6366f1}
.btn{width:100%;padding:13px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;margin-top:8px}
.btn:hover{background:#4f46e5}
.error{background:#7f1d1d;color:#fecaca;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;text-align:center}
.success{background:#064e3b;color:#a7f3d0;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;text-align:center}
</style>
</head>
<body>
<header>
<div class="nav">
<a href="/addons/chathub/index/landing" class="logo">💬 SITENAME</a>
<div class="user-info">
<a href="/addons/chathub/index/my">我的</a>
<a href="/addons/chathub/index/logout">退出</a>
</div>
</div>
</header>
<div class="container">
<div class="card">
<h1>修改密码</h1>
MSG_PLACEHOLDER
<form method="POST">
<div class="form-group">
<label>原密码</label>
<input type="password" name="old_password" class="form-control" required>
</div>
<div class="form-group">
<label>新密码（至少 6 位）</label>
<input type="password" name="new_password" class="form-control" required minlength="6">
</div>
<div class="form-group">
<label>确认新密码</label>
<input type="password" name="confirm_password" class="form-control" required minlength="6">
</div>
<button type="submit" class="btn">提交</button>
</form>
</div>
</div>
</body>
</html>
HTML;
        $html = str_replace('SITENAME', $siteName, $html);
        $html = str_replace('MSG_PLACEHOLDER', $msgHtml, $html);
        $this->render($html);
    }

    public function renew()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }
        $tenantId = (int)$this->request->get('id', 0);
        $tenant = Db::name('chathub_tenant')->where('id', $tenantId)->where('user_id', $userId)->find();
        if (!$tenant) {
            header('Location: /addons/chathub/index/my?error=' . urlencode('租户不存在'));
            exit;
        }
        $config = json_decode($tenant['config'] ?? '{}', true) ?: [];
        $plan = $config['plan'] ?? 'basic';
        $price = (int)($config['price'] ?? 0);
        $cfg = get_addon_config('chathub');
        $alipayOn = !empty($cfg['alipay_enabled']);
        $wechatOn = !empty($cfg['wechat_enabled']);
        $siteName = $cfg['site_name'] ?? 'ChatHub';

        $orderNo = 'CH' . date('YmdHis') . mt_rand(100, 999);
        Db::name('chathub_order')->insert([
            'order_no' => $orderNo,
            'tenant_id' => $tenant['id'],
            'user_id' => $userId,
            'plan' => $plan,
            'amount' => $price,
            'status' => 'pending',
            'createtime' => time(),
        ]);

        $payBtns = '';
        if ($alipayOn) {
            $payBtns .= '<a href="/addons/chathub/index/payAlipay?order=' . $orderNo . '" class="pay-btn alipay">💰 支付宝支付 ¥' . $price . '</a>';
        }
        if ($wechatOn) {
            $payBtns .= '<a href="/addons/chathub/index/payWechat?order=' . $orderNo . '" class="pay-btn wechat">💚 微信支付 ¥' . $price . '</a>';
        }
        if (!$alipayOn && !$wechatOn) {
            $payBtns = '<div class="notice">⚠️ 支付功能未开通，请联系客服手动续费</div>';
        }

        $planName = ['basic' => '基础版', 'pro' => '专业版', 'enterprise' => '企业版'][$plan] ?? $plan;
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>续费 - SITENAME</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:40px;max-width:480px;width:100%}
h1{color:#fff;font-size:24px;margin-bottom:8px;text-align:center}
.subtitle{color:#94a3b8;font-size:14px;text-align:center;margin-bottom:28px}
.details{background:#0f172a;border-radius:10px;padding:20px;margin-bottom:24px}
.row{display:flex;justify-content:space-between;padding:6px 0;font-size:14px}
.label{color:#94a3b8}
.value{color:#fff;font-weight:500}
.pay-btn{display:block;width:100%;padding:14px;margin:8px 0;border-radius:10px;text-align:center;text-decoration:none;font-weight:600;font-size:15px;transition:all .2s}
.alipay{background:#1677ff;color:#fff}
.alipay:hover{background:#0958d9}
.wechat{background:#07c160;color:#fff}
.wechat:hover{background:#06a050}
.notice{background:#7c2d12;color:#fed7aa;padding:12px;border-radius:8px;text-align:center;font-size:13px;margin:12px 0}
.back{display:block;text-align:center;color:#94a3b8;font-size:13px;margin-top:20px;text-decoration:none}
.back:hover{color:#fff}
</style>
</head>
<body>
<div class="card">
<h1>续费订阅</h1>
<p class="subtitle">订单号：ORDERNO</p>
<div class="details">
<div class="row"><span class="label">租户</span><span class="value">TENANT_NAME</span></div>
<div class="row"><span class="label">套餐</span><span class="value">PLAN_NAME</span></div>
<div class="row"><span class="label">席位数</span><span class="value">SEATS</span></div>
<div class="row"><span class="label">当前到期</span><span class="value">EXPIRE</span></div>
<div class="row" style="border-top:1px solid #1e293b;margin-top:8px;padding-top:12px"><span class="label">应付金额</span><span class="value" style="color:#10b981;font-size:18px">¥PRICE /月</span></div>
</div>
PAY_BUTTONS
<a href="/addons/chathub/index/my" class="back">← 返回会员中心</a>
</div>
</body>
</html>
HTML;
        $html = str_replace('SITENAME', $siteName, $html);
        $html = str_replace('ORDERNO', $orderNo, $html);
        $html = str_replace('TENANT_NAME', htmlspecialchars($tenant['tenant_name']), $html);
        $html = str_replace('PLAN_NAME', $planName, $html);
        $html = str_replace('SEATS', $tenant['max_agents'], $html);
        $html = str_replace('EXPIRE', $tenant['expire_at'] ? date('Y-m-d', strtotime($tenant['expire_at'])) : '-', $html);
        $html = str_replace('PRICE', $price, $html);
        $html = str_replace('PAY_BUTTONS', $payBtns, $html);
        $this->render($html);
    }

    private function _registerJson($code, $msg, $companyName, $plan, $price, $seats, $embedCode = '', $initialPassword = '', $expireAt = '')
    {
        header('Content-Type: application/json; charset=utf-8');
        exit(json_encode([
            'code' => $code, 'msg' => $msg,
            'company_name' => $companyName, 'plan' => $plan, 'price' => $price, 'seats' => $seats,
            'embed_code' => $embedCode, 'initial_password' => $initialPassword, 'expire_at' => $expireAt,
        ]));
    }

    private function _registerResultPage($success, $msg, $companyName = '', $plan = '', $price = 0, $seats = 0, $embedCode = '', $initialPassword = '')
    {
        $backUrl = '/addons/chathub/index/landing';
        $icon = $success ? '✓' : '✗';
        $color = $success ? '#10b981' : '#ef4444';
        $planName = ['basic' => '基础版', 'pro' => '专业版', 'enterprise' => '企业版'][$plan] ?? $plan;

        echo '<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>注册结果 - ChatHub</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#fff;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{background:#1e293b;border-radius:16px;padding:48px 40px;max-width:600px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.icon{width:80px;height:80px;border-radius:50%;background:' . $color . ';color:#fff;font-size:48px;display:flex;align-items:center;justify-content:center;margin:0 auto 24px}
h1{text-align:center;font-size:24px;margin-bottom:12px}
.msg{text-align:center;color:#94a3b8;font-size:16px;margin-bottom:32px;line-height:1.6}
.details{background:#0f172a;border-radius:12px;padding:24px;margin-bottom:24px}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e293b}
.row:last-child{border:none}
.label{color:#94a3b8;font-size:14px}
.value{color:#fff;font-weight:500}
.embed{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;margin:16px 0;font-family:monospace;font-size:12px;color:#94a3b8;word-break:break-all;max-height:200px;overflow-y:auto}
.btn{display:block;width:100%;padding:14px;border-radius:8px;border:none;font-size:16px;font-weight:600;cursor:pointer;text-align:center;text-decoration:none;margin-top:12px}
.btn-primary{background:#6366f1;color:#fff}
.btn-primary:hover{background:#4f46e5}
.btn-secondary{background:#334155;color:#fff}
</style>
</head>
<body>
<div class="card">
<div class="icon">' . $icon . '</div>
<h1>' . ($success ? '注册成功' : '注册失败') . '</h1>
<p class="msg">' . htmlspecialchars($msg) . '</p>';

        if ($success && $companyName) {
            echo '<div class="details">';
            echo '<div class="row"><span class="label">公司名称</span><span class="value">' . htmlspecialchars($companyName) . '</span></div>';
            echo '<div class="row"><span class="label">套餐</span><span class="value">' . htmlspecialchars($planName) . '（¥' . $price . '/月）</span></div>';
            echo '<div class="row"><span class="label">席位</span><span class="value">' . $seats . '</span></div>';
            echo '<div class="row"><span class="label">到期时间</span><span class="value">' . date('Y-m-d', strtotime('+30 days')) . '</span></div>';
            echo '</div>';

            if ($embedCode) {
                echo '<p style="color:#94a3b8;font-size:14px;margin-bottom:8px">嵌入代码（复制到您的网站）：</p>';
                echo '<div class="embed">' . htmlspecialchars($embedCode) . '</div>';
            }

            if ($initialPassword) {
                echo '<div style="background:#7c2d12;border:1px solid #ea580c;border-radius:10px;padding:16px;margin:20px 0;text-align:left">';
                echo '<p style="color:#fed7aa;font-size:13px;margin-bottom:6px">⚠️ 您的登录密码（请保存，登录后可修改）：</p>';
                echo '<div style="font-family:monospace;font-size:20px;color:#fff;font-weight:700;letter-spacing:2px;text-align:center;padding:8px;background:#0f172a;border-radius:6px">' . htmlspecialchars($initialPassword) . '</div>';
                echo '<p style="color:#fdba74;font-size:12px;margin-top:8px;text-align:center">登录邮箱：' . htmlspecialchars($companyName) . '</p>';
                echo '</div>';
            }
        }

        echo '<a href="/addons/chathub/index/login" class="btn btn-primary">立即登录</a>';
        echo '<a href="' . $backUrl . '" class="btn btn-secondary">返回首页</a>';
        echo '</div></body></html>';
        exit;
    }

    public function del($ids = null)
    {
        $ids = $ids ?: $this->request->post('ids') ?: $this->request->param('ids');
        if ($ids) {
            Db::startTrans();
            try {
                $count = $this->model->where($this->model->getPk(), 'in', $ids)->delete();
                Db::commit();
            } catch (\Exception $e) {
                Db::rollback();
                $this->error($e->getMessage());
            }
            if ($count) $this->success('删除成功！');
            $this->error('没有删除任何记录');
        }
        $this->error('参数不能为空');
    }

    public function dashboard()
    {
        $logs = Db::name('chathub_log')->order('createtime desc')->limit(10)->select();
        $html = '<div class="nav">
            <a href="/pGTnXkhdmy.php/addons/chathub/index/index" class="active">租户列表</a>
            <a href="/pGTnXkhdmy.php/addons/chathub/index/add">添加租户</a>
        </div>
        <div class="stats">
            <div class="stat-card"><div class="number">' . $this->model->count() . '</div><div class="label">总租户</div></div>
            <div class="stat-card"><div class="number">' . $this->model->where("status","active")->count() . '</div><div class="label">已开通</div></div>
            <div class="stat-card"><div class="number">' . $this->model->where("status","pending")->count() . '</div><div class="label">待开通</div></div>
            <div class="stat-card"><div class="number">24/7</div><div class="label">AI 在线</div></div>
        </div>
        <div class="card"><div class="card-header"><h2>最近操作</h2></div><div class="card-body">';
        if ($logs) {
            $html .= '<table><thead><tr><th>操作</th><th>状态</th><th>时间</th></tr></thead><tbody>';
            foreach ($logs as $log) {
                $html .= '<tr><td>' . htmlspecialchars($log['action']) . '</td>';
                $html .= '<td><span class="badge badge-' . ($log['status'] == 'success' ? 'success' : 'danger') . '">' . $log['status'] . '</span></td>';
                $html .= '<td>' . date('Y-m-d H:i', $log['createtime']) . '</td></tr>';
            }
            $html .= '</tbody></table>';
        } else {
            $html .= '<p style="text-align:center;color:#9ca3af;padding:40px">暂无操作记录</p>';
        }
        $html .= '</div></div>';
        $this->render($this->layout('控制面板', $html));
    }

    public function logs()
    {
        $logs = Db::name('chathub_log')->order('createtime desc')->paginate(20);
        $html = '<div class="nav"><a href="/pGTnXkhdmy.php/addons/chathub/index/dashboard">← 控制面板</a></div>
        <div class="card"><div class="card-header"><h2>操作日志</h2></div><div class="card-body">';
        if ($logs->items()) {
            $html .= '<table><thead><tr><th>租户ID</th><th>操作</th><th>状态</th><th>操作人</th><th>时间</th></tr></thead><tbody>';
            foreach ($logs->items() as $log) {
                $html .= '<tr><td>' . $log['tenant_id'] . '</td><td>' . htmlspecialchars($log['action']) . '</td>';
                $html .= '<td><span class="badge badge-' . ($log['status'] == 'success' ? 'success' : 'danger') . '">' . $log['status'] . '</span></td>';
                $html .= '<td>' . htmlspecialchars($log['operator']) . '</td>';
                $html .= '<td>' . date('Y-m-d H:i:s', $log['createtime']) . '</td></tr>';
            }
            $html .= '</tbody></table>';
        } else {
            $html .= '<p style="text-align:center;color:#9ca3af;padding:40px">暂无记录</p>';
        }
        $html .= '</div></div>';
        $this->render($this->layout('操作日志', $html));
    }

    public function suspend($ids = null)
    {
        $ids = $ids ?: $this->request->post('ids');
        if (!$ids) $this->error('参数不能为空');

        $row = $this->model->get($ids);
        if (!$row) $this->error('记录不存在');
        if ($row['status'] !== 'active') $this->error('只能暂停已开通的租户');

        // 调 provision 服务暂停（它负责禁 Chatwoot inbox + 停 QwenPaw Agent）
        $cfg = get_addon_config('chathub');
        $url = rtrim($cfg['provision_server_url'] ?? 'http://CoPaw:5566', '/') . '/suspend';
        $payload = json_encode([
            'inbox_id' => $row['inbox_id'],
            'tenant_name' => $row['tenant_name'],
            'domain' => $row['domain'],
        ]);
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true, CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-API-Key: chathub-default-key-change-me'],
            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30
        ]);
        $response = curl_exec($ch);
        $curlError = curl_error($ch);
        curl_close($ch);

        if ($curlError) {
            $this->error('暂停失败：无法连接 Provision 服务（' . $curlError . '）');
        }

        $resultData = json_decode($response, true);
        if ($resultData && isset($resultData['success'])) {
            $row->status = 'suspended';
            $row->save();
            Db::name('chathub_log')->insert([
                'tenant_id' => $row['id'], 'action' => 'suspend', 'detail' => $response,
                'status' => 'success', 'operator' => session('admin.username') ?: 'system', 'createtime' => time()
            ]);
            $this->success('已暂停');
        }

        $errorMsg = $resultData['error'] ?? $response ?? '未知错误';
        $this->error('暂停失败：' . $errorMsg);
    }

    public function activate($ids = null)
    {
        $ids = $ids ?: $this->request->post('ids');
        if (!$ids) $this->error('参数不能为空');

        $row = $this->model->get($ids);
        if (!$row) $this->error('记录不存在');
        if ($row['status'] !== 'suspended') $this->error('只能恢复已暂停的租户');

        $cfg = get_addon_config('chathub');
        $url = rtrim($cfg['provision_server_url'] ?? 'http://CoPaw:5566', '/') . '/activate';
        $payload = json_encode(['inbox_id' => $row['inbox_id']]);
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true, CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30
        ]);
        $response = curl_exec($ch);
        $curlError = curl_error($ch);
        curl_close($ch);

        if ($curlError) {
            $this->error('恢复失败：无法连接 Provision 服务（' . $curlError . '）');
        }

        $resultData = json_decode($response, true);
        if ($resultData && isset($resultData['success'])) {
            $row->status = 'active';
            $row->save();
            Db::name('chathub_log')->insert([
                'tenant_id' => $row['id'], 'action' => 'activate', 'detail' => $response,
                'status' => 'success', 'operator' => session('admin.username') ?: 'system', 'createtime' => time()
            ]);
            $this->success('已恢复');
        }

        $errorMsg = $resultData['error'] ?? $response ?? '未知错误';
        $this->error('恢复失败：' . $errorMsg);
    }

    public function setExpire($ids = null)
    {
        $ids = $ids ?: $this->request->post('ids');
        $expireAt = $this->request->post('expire_at');
        if (!$ids) $this->error('参数不能为空');
        if (!$expireAt) $this->error('请输入到期时间');

        $row = $this->model->get($ids);
        if (!$row) $this->error('记录不存在');

        $row->expire_at = $expireAt;
        $row->save();

        Db::name('chathub_log')->insert([
            'tenant_id' => $row['id'], 'action' => 'set_expire', 'detail' => '设置到期: ' . $expireAt,
            'status' => 'success', 'operator' => session('admin.username') ?: 'system', 'createtime' => time()
        ]);

        $this->success('到期时间已设置');
    }

    public function landing()
    {
        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChatHub - AI 智能客服多租户平台</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:#0f172a;color:#e2e8f0;line-height:1.6}
a{color:#818cf8;text-decoration:none}
a:hover{color:#a5b4fc}
header{background:#0f172a;border-bottom:1px solid #1e293b;padding:20px 0;position:sticky;top:0;z-index:100}
.nav{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:22px;font-weight:700;color:#fff;display:flex;align-items:center;gap:10px}
.logo-icon{width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px}
.nav-links{display:flex;gap:32px;align-items:center}
.nav-links a{color:#cbd5e1;font-size:15px;font-weight:500}
.nav-links a:hover{color:#fff}
.btn{display:inline-block;padding:10px 24px;border-radius:8px;font-weight:600;font-size:14px;transition:all .2s;border:none;cursor:pointer}
.btn-primary{background:#6366f1;color:#fff}
.btn-primary:hover{background:#4f46e5;color:#fff;transform:translateY(-1px)}
.btn-outline{border:1px solid #334155;color:#e2e8f0;background:transparent}
.btn-outline:hover{border-color:#6366f1;color:#fff}
.hero{max-width:1200px;margin:0 auto;padding:100px 24px 80px;text-align:center}
.hero h1{font-size:56px;font-weight:800;color:#fff;line-height:1.15;margin-bottom:24px;letter-spacing:-1px}
.hero h1 .grad{background:linear-gradient(135deg,#818cf8,#c084fc,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.hero p{font-size:20px;color:#94a3b8;max-width:720px;margin:0 auto 40px;line-height:1.7}
.hero-cta{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn-lg{padding:16px 36px;font-size:16px;border-radius:10px}
.features{max-width:1200px;margin:0 auto;padding:80px 24px}
.section-title{text-align:center;margin-bottom:60px}
.section-title h2{font-size:40px;font-weight:700;color:#fff;margin-bottom:16px}
.section-title p{font-size:18px;color:#94a3b8}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.feature{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:32px;transition:all .3s}
.feature:hover{transform:translateY(-4px);border-color:#6366f1;box-shadow:0 20px 40px rgba(99,102,241,.15)}
.feature-icon{width:52px;height:52px;border-radius:12px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:20px}
.feature h3{color:#fff;font-size:20px;font-weight:600;margin-bottom:12px}
.feature p{color:#94a3b8;font-size:15px;line-height:1.7}
.pricing{max-width:1200px;margin:0 auto;padding:80px 24px}
.pricing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:50px}
.plan{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:36px 32px;position:relative;transition:all .3s}
.plan:hover{transform:translateY(-4px)}
.plan.featured{border-color:#6366f1;background:linear-gradient(180deg,#1e293b 0%,#1e1b4b 100%);transform:scale(1.05)}
.plan.featured::before{content:"推荐";position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#6366f1;color:#fff;padding:4px 16px;border-radius:20px;font-size:12px;font-weight:600}
.plan h3{color:#fff;font-size:22px;font-weight:600;margin-bottom:8px}
.plan .price{font-size:42px;font-weight:800;color:#fff;margin:20px 0 8px}
.plan .price small{font-size:16px;color:#94a3b8;font-weight:500}
.plan .desc{color:#94a3b8;font-size:14px;margin-bottom:24px}
.plan ul{list-style:none;margin-bottom:32px}
.plan ul li{padding:8px 0;color:#cbd5e1;font-size:14px;display:flex;align-items:center;gap:10px}
.plan ul li::before{content:"✓";color:#10b981;font-weight:700}
.plan .btn{width:100%;text-align:center;padding:14px;font-size:15px}
.cta-section{background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:24px;padding:60px 40px;text-align:center;margin:80px auto;max-width:1200px}
.cta-section h2{color:#fff;font-size:32px;font-weight:700;margin-bottom:16px}
.cta-section p{color:#e0e7ff;font-size:18px;margin-bottom:32px}
.cta-section .btn{background:#fff;color:#6366f1}
.cta-section .btn:hover{background:#f1f5f9;transform:translateY(-2px)}
footer{background:#0f172a;border-top:1px solid #1e293b;padding:40px 24px;text-align:center;color:#64748b;font-size:14px}
footer a{color:#94a3b8;margin:0 12px}
@media (max-width:768px){
.hero h1{font-size:36px}
.hero p{font-size:16px}
.grid,.pricing-grid{grid-template-columns:1fr}
.plan.featured{transform:none}
.section-title h2{font-size:28px}
}
</style>
</head>
<body>
<header>
<div class="nav">
<a href="/addons/chathub/index/landing" class="logo"><div class="logo-icon">💬</div>ChatHub</a>
<div class="nav-links">
<a href="#features">功能特性</a>
<a href="#pricing">套餐价格</a>
<a href="/addons/chathub/index/registerpage" class="btn btn-primary">立即注册</a>
</div>
</div>
</header>

<section class="hero">
<h1>AI 智能客服<br><span class="grad">多租户 SaaS 平台</span></h1>
<p>基于 Chatwoot + QwenPaw Agent，为企业打造一站式 AI 客服解决方案。<br>多租户隔离、按席位计费、3 分钟开通。</p>
<div class="hero-cta">
<a href="/addons/chathub/index/registerpage" class="btn btn-primary btn-lg">免费注册</a>
<a href="#pricing" class="btn btn-outline btn-lg">查看套餐</a>
</div>
</section>

<section class="features" id="features">
<div class="section-title">
<h2>核心功能</h2>
<p>企业级 AI 客服所需的一切，开箱即用</p>
</div>
<div class="grid">
<div class="feature">
<div class="feature-icon">🏢</div>
<h3>多租户隔离</h3>
<p>每个租户独立 Chatwoot 团队、收件箱、Agent，数据完全隔离，互不干扰。</p>
</div>
<div class="feature">
<div class="feature-icon">🤖</div>
<h3>AI 智能应答</h3>
<p>接入 QwenPaw Agent 大模型，7×24 自动回复客户咨询，支持多轮对话和上下文理解。</p>
</div>
<div class="feature">
<div class="feature-icon">💬</div>
<h3>一键嵌入</h3>
<p>提供 JS 嵌入代码，复制粘贴即可集成到任何网站，5 分钟完成上线。</p>
</div>
<div class="feature">
<div class="feature-icon">📊</div>
<h3>实时监控</h3>
<p>会话量、响应时间、客户满意度等关键指标实时可见，运营决策有数。</p>
</div>
<div class="feature">
<div class="feature-icon">💳</div>
<h3>按席计费</h3>
<p>基础版¥50/月起，每加一个席位+¥10，灵活扩容，用多少付多少。</p>
</div>
<div class="feature">
<div class="feature-icon">🔒</div>
<h3>数据安全</h3>
<p>租户数据加密存储，HTTPS 全链路传输，符合企业级安全合规要求。</p>
</div>
</div>
</section>

<section class="pricing" id="pricing">
<div class="section-title">
<h2>套餐价格</h2>
<p>简单透明，按需选择，随时升级</p>
</div>
<div class="pricing-grid">
<div class="plan">
<h3>基础版</h3>
<div class="price">¥50<small>/月</small></div>
<p class="desc">适合个人或小团队</p>
<ul>
<li>1 个管理员席位</li>
<li>独立 Chatwoot 收件箱</li>
<li>AI 自动应答</li>
<li>1 个网站嵌入</li>
<li>邮件技术支持</li>
</ul>
<a href="/addons/chathub/index/registerpage?plan=basic" class="btn btn-outline">选择基础版</a>
</div>
<div class="plan featured">
<h3>专业版</h3>
<div class="price">¥60<small>/月</small></div>
<p class="desc">适合成长型团队</p>
<ul>
<li>2 个管理员席位</li>
<li>独立 Chatwoot 收件箱</li>
<li>AI 自动应答</li>
<li>3 个网站嵌入</li>
<li>优先技术支持</li>
</ul>
<a href="/addons/chathub/index/registerpage?plan=pro" class="btn btn-primary">选择专业版</a>
</div>
<div class="plan">
<h3>企业版</h3>
<div class="price">¥70<small>/月 起</small></div>
<p class="desc">适合中大型企业</p>
<ul>
<li>自定义席位（+¥10/席/月）</li>
<li>独立 Chatwoot 收件箱</li>
<li>AI 自动应答</li>
<li>不限网站嵌入</li>
<li>7×24 专属客服</li>
</ul>
<a href="/addons/chathub/index/registerpage?plan=enterprise" class="btn btn-outline">选择企业版</a>
</div>
</div>
</section>

<section class="cta-section">
<h2>3 分钟开通，立即拥有 AI 客服</h2>
<p>注册即送 30 天免费试用，无需信用卡</p>
<a href="/addons/chathub/index/registerpage" class="btn btn-lg">免费注册</a>
</section>

<footer>
<div>
<a href="/addons/chathub/index/landing">首页</a>·
<a href="/addons/chathub/index/registerpage">注册</a>·
<a href="/admin">管理后台</a>
</div>
<div style="margin-top:16px">© 2026 ChatHub. Powered by Chatwoot + QwenPaw</div>
</footer>
</body>
</html>
HTML;
        $html = str_replace('ChatHub', $siteName, $html);
        $this->render($html);
    }

    public function registerPage()
    {
        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';
        $plan = $this->request->get('plan', 'basic');
        if (!in_array($plan, ['basic', 'pro', 'enterprise'])) $plan = 'basic';
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>注册 ChatHub - AI 智能客服</title>
<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
header{background:#0f172a;border-bottom:1px solid #1e293b;padding:20px 0}
.nav{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:22px;font-weight:700;color:#fff;display:flex;align-items:center;gap:10px}
.logo-icon{width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px}
.nav-links a{color:#cbd5e1;margin-left:24px;font-size:14px}
.container{max-width:560px;margin:40px auto;padding:0 24px}
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:40px;box-shadow:0 20px 60px rgba(0,0,0,.3)}
h1{color:#fff;font-size:28px;font-weight:700;margin-bottom:8px}
.subtitle{color:#94a3b8;font-size:15px;margin-bottom:32px}
.form-group{margin-bottom:20px}
.form-group label{display:block;color:#cbd5e1;font-size:14px;font-weight:500;margin-bottom:8px}
.form-group label .req{color:#f87171}
.form-control{width:100%;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#fff;font-size:15px;transition:all .2s}
.form-control:focus{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15)}
.form-control::placeholder{color:#64748b}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.plan-selector{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.plan-option{background:#0f172a;border:2px solid #334155;border-radius:10px;padding:16px 12px;text-align:center;cursor:pointer;transition:all .2s}
.plan-option:hover{border-color:#475569}
.plan-option.selected{border-color:#6366f1;background:rgba(99,102,241,.1)}
.plan-option .name{color:#fff;font-weight:600;font-size:15px;margin-bottom:4px}
.plan-option .price{color:#94a3b8;font-size:13px}
.plan-option input{display:none}
.seats-row{display:none;margin-top:12px}
.seats-row.show{display:block}
.seats-row label{color:#94a3b8;font-size:13px}
.btn-primary{width:100%;padding:14px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;margin-top:8px;transition:all .2s}
.btn-primary:hover{background:#4f46e5}
.btn-primary:disabled{opacity:.6;cursor:not-allowed}
.btn-secondary{width:100%;padding:14px;background:transparent;color:#94a3b8;border:1px solid #334155;border-radius:8px;font-size:15px;cursor:pointer;margin-top:12px;text-align:center;display:block;text-decoration:none}
.btn-secondary:hover{border-color:#475569;color:#cbd5e1}
.result-card{text-align:center;padding:60px 40px}
.result-card .icon{width:80px;height:80px;border-radius:50%;margin:0 auto 24px;display:flex;align-items:center;justify-content:center;font-size:42px;font-weight:700}
.result-card.success .icon{background:#10b981;color:#fff}
.result-card.error .icon{background:#ef4444;color:#fff}
.result-card h2{color:#fff;font-size:26px;margin-bottom:12px}
.result-card p{color:#94a3b8;font-size:15px;margin-bottom:24px;line-height:1.7}
.result-details{background:#0f172a;border-radius:10px;padding:20px;margin:24px 0;text-align:left}
.result-details .row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e293b;font-size:14px}
.result-details .row:last-child{border:none}
.result-details .label{color:#94a3b8}
.result-details .value{color:#fff;font-weight:500}
.embed-code{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;font-family:monospace;font-size:12px;color:#94a3b8;word-break:break-all;max-height:200px;overflow-y:auto;margin:12px 0}
@media (max-width:600px){.form-row,.plan-selector{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
<div class="nav">
<a href="/addons/chathub/index/landing" class="logo"><div class="logo-icon">💬</div>ChatHub</a>
<div class="nav-links">
<a href="/addons/chathub/index/landing">首页</a>
<a href="/addons/chathub/index/registerpage">注册</a>
</div>
</div>
</header>

<div class="container">
<div class="card" id="form-card">
<h1>注册 ChatHub 账号</h1>
<p class="subtitle">注册后即可选择套餐，开通 AI 智能客服</p>

<form id="chathub-register" method="POST" action="/addons/chathub/index/register">
<div class="form-group">
<label>选择套餐 <span class="req">*</span></label>
<div class="plan-selector">
<label class="plan-option" data-plan="basic">
<input type="radio" name="plan" value="basic">
<div class="name">基础版</div>
<div class="price">¥50/月</div>
</label>
<label class="plan-option" data-plan="pro">
<input type="radio" name="plan" value="pro">
<div class="name">专业版</div>
<div class="price">¥60/月</div>
</label>
<label class="plan-option" data-plan="enterprise">
<input type="radio" name="plan" value="enterprise">
<div class="name">企业版</div>
<div class="price">¥70+/月</div>
</label>
</div>
</div>

<div class="form-group seats-row" id="seats-row">
<label>额外席位（管理员之外） <span class="req">*</span></label>
<input type="number" name="seats" id="seats-input" class="form-control" min="1" max="100" value="3" placeholder="每多一个席位 +¥10/月">
</div>

<div class="form-group">
<label>公司名称 <span class="req">*</span></label>
<input type="text" name="company_name" class="form-control" required placeholder="请输入公司名称">
</div>

<div class="form-group">
<label>联系邮箱 <span class="req">*</span></label>
<input type="email" name="email" class="form-control" required placeholder="将作为登录账号">
</div>

<div class="form-group">
<label>子域名 <span class="req">*</span></label>
<input type="text" name="domain" class="form-control" required placeholder="例如 mycompany" pattern="[a-z0-9-]+" title="只能小写字母、数字、横线">
</div>

<div class="form-group">
<label>备注</label>
<textarea name="notes" class="form-control" rows="3" placeholder="选填，如特殊需求、接入网站URL等"></textarea>
</div>

<button type="submit" class="btn-primary" id="submit-btn">注册并开通</button>
<a href="/addons/chathub/index/landing" class="btn-secondary">返回首页</a>
</form>
</div>
</div>

<script>
$(function(){
var preselect='PLAN_PLACEHOLDER';
if(preselect && $('input[name=plan][value='+preselect+']').length){
$('input[name=plan][value='+preselect+']').prop('checked',true).parent().addClass('selected');
if(preselect==='enterprise'){$('#seats-row').addClass('show');}
}
$('.plan-option').click(function(){
$('.plan-option').removeClass('selected');
$(this).addClass('selected');
$(this).find('input').prop('checked',true);
if($(this).data('plan')==='enterprise'){$('#seats-row').addClass('show');}else{$('#seats-row').removeClass('show');}
});
$('form').on('submit',function(e){
e.preventDefault();
var btn=$('#submit-btn');
btn.prop('disabled',true).text('开通中...');
$.ajax({
url:'/addons/chathub/index/register',
type:'POST',
dataType:'json',
data:$(this).serialize(),
success:function(r){
showResult(r.code===1,r.msg||(r.code===1?'注册成功':'注册失败'),r.data);
},
error:function(xhr){
showResult(false,'网络错误：'+xhr.statusText);
}
});
function showResult(ok,msg,data){
$('#form-card').html(
'<div class="result-card '+(ok?'success':'error')+'">'+
'<div class="icon">'+(ok?'✓':'✗')+'</div>'+
'<h2>'+(ok?'注册成功':'注册失败')+'</h2>'+
'<p>'+msg+'</p>'+
(data&&data.embed_code?'<div class="embed-code">'+data.embed_code+'</div>':'')+
(data?'<div class="result-details">':'')+
(data&&data.company_name?'<div class="row"><span class="label">公司名称</span><span class="value">'+data.company_name+'</span></div>':'')+
(data&&data.plan?'<div class="row"><span class="label">套餐</span><span class="value">'+data.plan+'</span></div>':'')+
(data&&data.seats?'<div class="row"><span class="label">席位</span><span class="value">'+data.seats+'</span></div>':'')+
(data&&data.expire_at?'<div class="row"><span class="label">到期时间</span><span class="value">'+data.expire_at+'</span></div>':'')+
'</div>'+
'<a href="/addons/chathub/index/registerpage" class="btn-secondary">继续注册</a>'+
'<a href="/addons/chathub/index/landing" class="btn-secondary" style="margin-top:8px">返回首页</a>'
);
}
});
});
</script>
</body>
</html>
HTML;
        $html = str_replace('PLAN_PLACEHOLDER', $plan, $html);
        $html = str_replace('ChatHub', $siteName, $html);
        $this->render($html);
    }

    public function login()
    {
        if (session('chathub_user_id')) {
            header('Location: /addons/chathub/index/my');
            exit;
        }
        $error = $this->request->get('error', '');
        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 - SITENAME</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.container{max-width:420px;width:100%}
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:40px;box-shadow:0 20px 60px rgba(0,0,0,.3)}
h1{color:#fff;font-size:26px;font-weight:700;margin-bottom:8px;text-align:center}
.subtitle{color:#94a3b8;font-size:14px;margin-bottom:32px;text-align:center}
.form-group{margin-bottom:18px}
.form-group label{display:block;color:#cbd5e1;font-size:13px;font-weight:500;margin-bottom:6px}
.form-control{width:100%;padding:12px 16px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#fff;font-size:15px;transition:all .2s}
.form-control:focus{outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15)}
.btn{width:100%;padding:13px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;margin-top:8px;transition:all .2s}
.btn:hover{background:#4f46e5}
.error{background:#7f1d1d;color:#fecaca;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;text-align:center}
.links{margin-top:20px;text-align:center;font-size:13px;color:#94a3b8}
.links a{color:#818cf8;text-decoration:none;margin:0 8px}
.links a:hover{color:#a5b4fc}
</style>
</head>
<body>
<div class="container">
<div class="card">
<h1>登录 SITENAME</h1>
<p class="subtitle">登录后查看您的 AI 客服订阅</p>
ERROR_PLACEHOLDER
<form method="POST" action="/addons/chathub/index/doLogin">
<div class="form-group">
<label>邮箱</label>
<input type="email" name="email" class="form-control" required placeholder="注册时使用的邮箱">
</div>
<div class="form-group">
<label>密码</label>
<input type="password" name="password" class="form-control" required placeholder="请输入密码">
</div>
<button type="submit" class="btn">登录</button>
</form>
<div class="links">
<a href="/addons/chathub/index/registerpage">还没账号？立即注册</a>·
<a href="/addons/chathub/index/landing">返回首页</a>
</div>
</div>
</div>
</body>
</html>
HTML;
        $html = str_replace('SITENAME', $siteName, $html);
        $errorHtml = $error ? '<div class="error">' . htmlspecialchars($error) . '</div>' : '';
        $html = str_replace('ERROR_PLACEHOLDER', $errorHtml, $html);
        $this->render($html);
    }

    public function doLogin()
    {
        $email = trim($this->request->post('email', ''));
        $password = $this->request->post('password', '');

        if (!$email || !$password) {
            header('Location: /addons/chathub/index/login?error=' . urlencode('请填写邮箱和密码'));
            exit;
        }

        $user = Db::name('user')->where('email', $email)->find();
        if (!$user) {
            header('Location: /addons/chathub/index/login?error=' . urlencode('邮箱或密码错误'));
            exit;
        }

        $hashOk = false;
        if (!empty($user['salt'])) {
            $hashOk = (md5($password) === $user['password']);
        } else {
            $hashOk = password_verify($password, $user['password']);
        }
        if (!$hashOk) {
            header('Location: /addons/chathub/index/login?error=' . urlencode('邮箱或密码错误'));
            exit;
        }

        session('chathub_user_id', $user['id']);
        session('chathub_user_email', $user['email']);
        session('chathub_user_nick', $user['nickname'] ?: $user['username']);

        Db::name('user')->where('id', $user['id'])->update([
            'logintime' => time(),
            'loginip' => $this->request->ip(),
            'prevtime' => $user['logintime'] ?: time(),
            'successions' => $user['successions'] + 1,
        ]);

        header('Location: /addons/chathub/index/my');
        exit;
    }

    public function logout()
    {
        session('chathub_user_id', null);
        session('chathub_user_email', null);
        session('chathub_user_nick', null);
        header('Location: /addons/chathub/index/landing');
        exit;
    }

    public function my()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }

        $user = Db::name('user')->where('id', $userId)->find();
        if (!$user) {
            session('chathub_user_id', null);
            header('Location: /addons/chathub/index/login?error=' . urlencode('账号不存在'));
            exit;
        }

        $tenants = Db::name('chathub_tenant')->where('user_id', $userId)
            ->order('id desc')->select();

        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';

        $flash = '';
        $order = $this->request->param('order');
        if ($this->request->param('just_paid')) {
            $flash = '<div style="background:#10b98122;border:1px solid #10b981;color:#34d399;padding:14px 20px;border-radius:10px;margin-bottom:18px">🎉 付款成功！您的 AI 客服已激活。如未显示嵌入代码，请点下方"嵌入代码"按钮获取。</div>';
        } elseif ($this->request->param('provisioning')) {
            $flash = '<div style="background:#3b82f622;border:1px solid #3b82f6;color:#60a5fa;padding:14px 20px;border-radius:10px;margin-bottom:18px">⚡ 正在为您开通资源（订单 ' . htmlspecialchars($order ?? '') . '），通常 30 秒内完成，请稍后刷新页面。如长时间未完成，可点"重新开通"按钮。</div>';
        } elseif ($this->request->param('pending')) {
            $flash = '<div style="background:#f59e0b22;border:1px solid #f59e0b;color:#fbbf24;padding:14px 20px;border-radius:10px;margin-bottom:18px">⏳ 付款确认中（订单 ' . htmlspecialchars($order ?? '') . '），请稍候 30 秒后刷新页面。</div>';
        } elseif ($err = $this->request->param('error')) {
            $flash = '<div style="background:#ef444422;border:1px solid #ef4444;color:#f87171;padding:14px 20px;border-radius:10px;margin-bottom:18px">⚠️ ' . htmlspecialchars($err) . '</div>';
        }

        $rows = '';
        foreach ($tenants as $t) {
            $statusBadge = ['active' => '#10b981', 'provisioning' => '#3b82f6', 'pending' => '#f59e0b', 'suspended' => '#ef4444', 'disabled' => '#6b7280'];
            $statusLabel = ['active' => '运行中', 'provisioning' => '开通中', 'pending' => '待开通', 'suspended' => '已暂停', 'disabled' => '已停用'];
            $color = $statusBadge[$t['status']] ?? '#6b7280';
            $label = $statusLabel[$t['status']] ?? $t['status'];
            $config = json_decode($t['config'] ?? '{}', true) ?: [];
            $planName = ['basic' => '基础版', 'pro' => '专业版', 'enterprise' => '企业版'][$config['plan'] ?? ''] ?? ($config['plan'] ?? '-');
            $price = $config['price'] ?? 0;
            $expire = $t['expire_at'] ? date('Y-m-d', strtotime($t['expire_at'])) : '-';
            $daysLeft = $t['expire_at'] ? max(0, (strtotime($t['expire_at']) - time()) / 86400) : 0;
            $daysLeftInt = (int)$daysLeft;
            $embed = $t['embed_code'] ?: '暂未生成';
            $embedEsc = htmlspecialchars($embed);
            $hasEmbed = !empty($t['embed_code']);

            $reprovBtn = !$hasEmbed
                ? '<a href="/addons/chathub/index/reprovision?ids=' . $t['id'] . '" class="btn-sm" style="background:#3b82f6;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block;margin-right:4px" onclick="return confirm(\'确认重新开通资源？\')">重新开通</a>'
                : '';

            $rows .= '<tr>
<td style="padding:14px 16px;border-bottom:1px solid #334155;color:#fff;font-weight:500">' . htmlspecialchars($t['tenant_name']) . '<br><span style="color:#64748b;font-size:12px;font-weight:400">' . htmlspecialchars($t['domain']) . '</span></td>
<td style="padding:14px 16px;border-bottom:1px solid #334155"><span style="background:' . $color . '22;color:' . $color . ';padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600">' . $label . '</span></td>
<td style="padding:14px 16px;border-bottom:1px solid #334155;color:#cbd5e1">' . $planName . '<br><span style="color:#64748b;font-size:12px">¥' . $price . '/月 · ' . $t['max_agents'] . '席</span></td>
<td style="padding:14px 16px;border-bottom:1px solid #334155;color:#cbd5e1">' . $expire . '<br><span style="color:#64748b;font-size:12px">剩 ' . $daysLeftInt . ' 天</span></td>
<td style="padding:14px 16px;border-bottom:1px solid #334155;text-align:right">
' . $reprovBtn . '
<button onclick="showEmbed(\'' . $embedEsc . '\')" class="btn-sm" style="background:#6366f1;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;margin-right:4px">嵌入代码</button>
' . ($daysLeftInt < 7 ? '<a href="/addons/chathub/index/renew?id=' . $t['id'] . '" class="btn-sm" style="background:#f59e0b;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;text-decoration:none;display:inline-block">续费</a>' : '') . '
</td>
</tr>';
        }

        if (empty($rows)) {
            $rows = '<tr><td colspan="5" style="padding:60px 20px;text-align:center;color:#64748b">还没有租户，<a href="/addons/chathub/index/registerpage" style="color:#818cf8">立即注册</a></td></tr>';
        }

        $nick = htmlspecialchars($user['nickname'] ?: $user['username'] ?: $user['email']);

        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>会员中心 - SITENAME</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
header{background:#0f172a;border-bottom:1px solid #1e293b;padding:18px 0}
.nav{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
.logo{font-size:20px;font-weight:700;color:#fff;display:flex;align-items:center;gap:10px}
.logo-icon{width:32px;height:32px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:16px}
.user-info{display:flex;align-items:center;gap:16px;font-size:14px}
.user-info .nick{color:#cbd5e1}
.user-info a{color:#94a3b8;text-decoration:none;font-size:13px}
.user-info a:hover{color:#fff}
.container{max-width:1200px;margin:30px auto;padding:0 24px}
.welcome{background:linear-gradient(135deg,#1e293b,#1e1b4b);border:1px solid #334155;border-radius:14px;padding:28px 32px;margin-bottom:24px}
.welcome h1{color:#fff;font-size:22px;font-weight:600;margin-bottom:6px}
.welcome p{color:#94a3b8;font-size:14px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}
.stat{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:18px 20px}
.stat .num{font-size:28px;font-weight:700;color:#fff;line-height:1.2}
.stat .lbl{color:#94a3b8;font-size:12px;margin-top:4px}
.table-card{background:#1e293b;border:1px solid #334155;border-radius:14px;overflow:hidden}
.table-card h2{color:#fff;font-size:16px;font-weight:600;padding:18px 24px;border-bottom:1px solid #334155;margin:0}
table{width:100%;border-collapse:collapse}
th{padding:12px 16px;background:#0f172a;color:#94a3b8;font-size:12px;font-weight:600;text-align:left;text-transform:uppercase}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:#1e293b;border:1px solid #334155;border-radius:14px;padding:30px;max-width:700px;width:100%;max-height:80vh;overflow:auto}
.modal-content h3{color:#fff;font-size:18px;margin-bottom:16px}
.modal-content pre{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;font-size:12px;color:#94a3b8;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.modal-content .close{float:right;background:none;border:none;color:#94a3b8;font-size:24px;cursor:pointer}
@media (max-width:768px){.stats{grid-template-columns:repeat(2,1fr)}th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4){display:none}}
</style>
</head>
<body>
<header>
<div class="nav">
<a href="/addons/chathub/index/landing" class="logo"><div class="logo-icon">💬</div>SITENAME</a>
<div class="user-info">
<span class="nick">👤 NICK_PLACEHOLDER</span>
<a href="/addons/chathub/index/my">我的</a>
<a href="/addons/chathub/index/changePassword">改密</a>
<a href="/addons/chathub/index/logout">退出</a>
</div>
</div>
</header>

<div class="container">
<div class="welcome">
<h1>欢迎回来，NICK_PLACEHOLDER</h1>
<p>管理您的 AI 客服订阅、查看嵌入代码、续费套餐</p>
</div>

FLASH_MESSAGE

<div class="stats">
<div class="stat"><div class="num">TENANT_COUNT</div><div class="lbl">租户总数</div></div>
<div class="stat"><div class="num">ACTIVE_COUNT</div><div class="lbl">运行中</div></div>
<div class="stat"><div class="num">TOTAL_SEATS</div><div class="lbl">总席位数</div></div>
<div class="stat"><div class="num">¥MONTHLY_TOTAL</div><div class="lbl">月费合计</div></div>
</div>

<div class="table-card">
<h2>我的租户</h2>
<table>
<thead>
<tr><th>租户</th><th>状态</th><th>套餐</th><th>到期</th><th style="text-align:right">操作</th></tr>
</thead>
<tbody>
TENANT_ROWS
</tbody>
</table>
</div>

<div class="table-card" style="margin-top:24px">
<h2>渠道管理</h2>
<p style="color:#64748b;font-size:13px;margin-bottom:12px">为您的客服租户绑定 Amazon / JD / Taobao / PDD / TikTok 等外部平台凭证。绑定后，AI 会在收到含商品 ASIN/SKU 的消息时，自动调用平台 API 拉取实时信息（如价格、库存），让回答更准确。</p>
<a href="/addons/chathub/index/channelList" class="btn-sm" style="display:inline-block;padding:8px 18px;background:#3b82f6;color:#fff;border-radius:6px;text-decoration:none">前往渠道管理 →</a>
</div>
</div>

<div class="modal" id="embedModal" onclick="if(event.target==this)closeEmbed()">
<div class="modal-content">
<button class="close" onclick="closeEmbed()">×</button>
<h3>嵌入代码</h3>
<p style="color:#94a3b8;font-size:13px;margin-bottom:12px">复制以下代码到您的网站 &lt;/body&gt; 之前：</p>
<pre id="embedCode"></pre>
</div>
</div>

<script>
function showEmbed(code){
if(!code||code==='暂未生成'){alert('嵌入代码暂未生成，请稍后查看');return}
document.getElementById('embedCode').textContent=code;
document.getElementById('embedModal').classList.add('show');
}
function closeEmbed(){
document.getElementById('embedModal').classList.remove('show');
}
</script>
</body>
</html>
HTML;

        $tenantCount = count($tenants);
        $activeCount = 0;
        $totalSeats = 0;
        $monthlyTotal = 0;
        foreach ($tenants as $t) {
            if ($t['status'] === 'active') $activeCount++;
            $totalSeats += (int)$t['max_agents'];
            $cfg_t = json_decode($t['config'] ?? '{}', true) ?: [];
            $monthlyTotal += (int)($cfg_t['price'] ?? 0);
        }

        $html = str_replace('SITENAME', $siteName, $html);
        $html = str_replace('NICK_PLACEHOLDER', $nick, $html);
        $html = str_replace('TENANT_COUNT', $tenantCount, $html);
        $html = str_replace('ACTIVE_COUNT', $activeCount, $html);
        $html = str_replace('TOTAL_SEATS', $totalSeats, $html);
        $html = str_replace('MONTHLY_TOTAL', $monthlyTotal, $html);
        $html = str_replace('TENANT_ROWS', $rows, $html);
        $html = str_replace('FLASH_MESSAGE', $flash, $html);

        $this->render($html);
    }

    public function channelList()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }
        $tenant = Db::name('chathub_tenant')->where('user_id', $userId)->order('id desc')->find();
        if (!$tenant) {
            header('Location: /addons/chathub/index/my?error=' . urlencode('请先开通租户'));
            exit;
        }
        $tenantId = (int)$tenant['id'];

        $rows = Db::name('chathub_channel_account')
            ->where('tenant_id', $tenantId)
            ->order('id DESC')
            ->select();

        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';

        $channels = ['web_widget', 'amazon', 'jd', 'taobao', 'pdd', 'tiktok'];
        $byChannel = [];
        foreach ($rows as $r) {
            $byChannel[$r['channel']] = $r;
        }

        $channelRows = '';
        foreach ($channels as $ch) {
            $r = $byChannel[$ch] ?? null;
            if ($r) {
                $status = $r['status'] === 'active' ? '已绑定' : '已停用';
                $cls = $r['status'] === 'active' ? 'badge-green' : 'badge-gray';
                $authAt = $r['last_refresh_at'] ?: '-';
                $channelRows .= "<tr><td>{$ch}</td><td><span class=\"badge {$cls}\">{$status}</span></td><td>{$authAt}</td><td><a class=\"btn-sm\" href=\"/addons/chathub/index/channelAuth?channel={$ch}\">管理</a></td></tr>";
            } else {
                $channelRows .= "<tr><td>{$ch}</td><td><span class=\"badge badge-gray\">未配置</span></td><td>-</td><td><a class=\"btn-sm btn-primary\" href=\"/addons/chathub/index/channelAuth?channel={$ch}\">去绑定</a></td></tr>";
            }
        }

        $html = <<<HTML
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>渠道管理 - {$siteName}</title>
<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f8fafc;margin:0;padding:24px;color:#1e293b}
.wrap{max-width:960px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,0.05)}
h1{margin:0 0 16px;font-size:24px}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{padding:12px;text-align:left;border-bottom:1px solid #e2e8f0}
th{background:#f1f5f9;font-weight:600;font-size:13px;color:#475569}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px}
.badge-green{background:#d1fae5;color:#065f46}
.badge-gray{background:#e2e8f0;color:#475569}
.btn-sm{display:inline-block;padding:6px 14px;border-radius:6px;background:#e2e8f0;color:#1e293b;text-decoration:none;font-size:13px}
.btn-sm:hover{background:#cbd5e1}
.btn-primary{background:#3b82f6;color:#fff}
.btn-primary:hover{background:#2563eb}
</style>
</head>
<body>
<div class="wrap">
<h1>渠道管理</h1>
<p>管理您已开通的客服渠道凭证。Amazon / JD / Taobao / PDD 凭证在服务端加密存储，不在浏览器暴露。</p>
<table>
<thead><tr><th>渠道</th><th>状态</th><th>授权时间</th><th>操作</th></tr></thead>
<tbody>{$channelRows}</tbody>
</table>
<p style="margin-top:24px"><a href="/addons/chathub/index/my">← 返回会员中心</a></p>
</div>
</body>
</html>
HTML;
        $this->render($html);
    }

    public function channelAuth()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }
        $tenant = Db::name('chathub_tenant')->where('user_id', $userId)->order('id desc')->find();
        if (!$tenant) {
            header('Location: /addons/chathub/index/my?error=' . urlencode('请先开通租户'));
            exit;
        }
        $tenantId = (int)$tenant['id'];
        $channel = input('get.channel', 'amazon');
        $allowed = ['web_widget', 'amazon', 'jd', 'taobao', 'pdd', 'tiktok'];
        if (!in_array($channel, $allowed, true)) {
            header('Location: /addons/chathub/index/channelList?error=' . urlencode('不支持的渠道'));
            exit;
        }

        $cfg = get_addon_config('chathub');
        $siteName = $cfg['site_name'] ?? 'ChatHub';

        if (request()->isPost()) {
            if ($channel === 'amazon') {
                $accessToken = trim((string)input('post.access_token', ''));
                $partnerTag  = trim((string)input('post.partner_tag', ''));
                $marketplace = trim((string)input('post.marketplace', 'us'));
                if ($accessToken === '' || $partnerTag === '') {
                    header('Location: /addons/chathub/index/channelAuth?channel=amazon&error=' . urlencode('Access Token 和 Partner Tag 必填'));
                    exit;
                }
                $credArr = [
                    'access_token' => $accessToken,
                    'partner_tag'  => $partnerTag,
                    'marketplace'  => in_array($marketplace, ['us','jp','de','uk','fr','it','es','ca','in','br','mx','au','sg'], true) ? $marketplace : 'us',
                ];
            } else {
                $appId = trim((string)input('post.app_id', ''));
                $appSecret = trim((string)input('post.app_secret', ''));
                $refreshToken = trim((string)input('post.refresh_token', ''));
                if ($appId === '' || $appSecret === '') {
                    header('Location: /addons/chathub/index/channelAuth?channel=' . urlencode($channel) . '&error=' . urlencode('App ID 和 App Secret 必填'));
                    exit;
                }
                $credArr = [
                    'app_id' => $appId,
                    'app_secret' => $appSecret,
                    'refresh_token' => $refreshToken,
                ];
            }
            $credJson = json_encode($credArr, JSON_UNESCAPED_UNICODE);

            $row = Db::name('chathub_channel_account')
                ->where('tenant_id', $tenantId)
                ->where('channel', $channel)
                ->find();
            $now = time();
            $data = [
                'tenant_id' => $tenantId,
                'channel' => $channel,
                'credentials_encrypted' => $credJson,
                'status' => 'active',
                'updatetime' => $now,
            ];
            if ($row) {
                Db::name('chathub_channel_account')->where('id', $row['id'])->update($data);
            } else {
                $data['createtime'] = $now;
                Db::name('chathub_channel_account')->insert($data);
            }
            header('Location: /addons/chathub/index/channelList');
            exit;
        }

        $existing = Db::name('chathub_channel_account')
            ->where('tenant_id', $tenantId)
            ->where('channel', $channel)
            ->find();

        if ($channel === 'amazon') {
            $formBody = <<<'AMAZON'
<p><label>Access Token (LWA 登录后获取)<br><input name="access_token" required style="width:100%;padding:8px"></label></p>
<p><label>Partner Tag (Associates 标签, 形如 mytag-20)<br><input name="partner_tag" required style="width:100%;padding:8px"></label></p>
<p><label>Marketplace<br>
<select name="marketplace" style="width:100%;padding:8px">
<option value="us">US (amazon.com)</option>
<option value="jp">JP (amazon.co.jp)</option>
<option value="de">DE (amazon.de)</option>
<option value="uk">UK (amazon.co.uk)</option>
<option value="fr">FR (amazon.fr)</option>
<option value="it">IT (amazon.it)</option>
<option value="es">ES (amazon.es)</option>
<option value="ca">CA (amazon.ca)</option>
<option value="in">IN (amazon.in)</option>
<option value="br">BR (amazon.com.br)</option>
<option value="mx">MX (amazon.com.mx)</option>
<option value="au">AU (amazon.com.au)</option>
<option value="sg">SG (amazon.sg)</option>
</select>
</label></p>
AMAZON;
            $hint = 'Amazon PA-API 5 凭证：Access Token 是 LWA (Login with Amazon) 流程获得的 Bearer Token，Partner Tag 在 Amazon Associates 后台获取。Marketplace 决定商品数据所在站点。';
        } else {
            $formBody = <<<'OTHER'
<p><label>App ID<br><input name="app_id" required style="width:100%;padding:8px"></label></p>
<p><label>App Secret<br><input name="app_secret" type="password" required style="width:100%;padding:8px"></label></p>
<p><label>Refresh Token (可选)<br><input name="refresh_token" style="width:100%;padding:8px"></label></p>
OTHER;
            $hint = '凭证会加密保存在服务端数据库（chathub 表 fa_chathub_channel_account）。Worker 通过 GATEWAY_AES_KEY 解密后调用对应平台 API。';
        }

        $html = <<<HTML
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>绑定渠道 - {$siteName}</title>
<script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
</head>
<body>
<div class="wrap">
<h1>绑定 {$channel}</h1>
<form method="post" action="/addons/chathub/index/channelAuth?channel={$channel}">
{$formBody}
<p><button type="submit" class="btn-primary">保存</button> <a href="/addons/chathub/index/channelList">取消</a></p>
</form>
<p style="margin-top:24px;color:#64748b;font-size:13px">{$hint}</p>
</div>
</body>
</html>
HTML;
        $this->render($html);
    }

    public function channelCallback()
    {
        header('Content-Type: text/plain; charset=utf-8');
        echo '未启用 OAuth 回调。请使用 /addons/chathub/index/channelAuth 表单直接绑定 App Secret。';
        exit;
    }

    public function payAlipay()
    {
        $orderNo = $this->request->get('order');
        $order = Db::name('chathub_order')->where('order_no', $orderNo)->find();
        if (!$order) { exit('订单不存在'); }
        $cfg = get_addon_config('chathub');
        if (empty($cfg['alipay_enabled'])) { exit('支付宝未启用'); }
        if (empty($cfg['alipay_app_id']) || empty($cfg['alipay_merchant_private_key'])) {
            exit('支付宝未配置完成，请在后台「插件管理 → ChatHub → 配置」填写 APPID 和私钥');
        }
        Db::name('chathub_order')->where('id', $order['id'])->update(['pay_method' => 'alipay', 'updatetime' => time()]);
        $gateway = !empty($cfg['alipay_sandbox']) ? 'https://openapi.alipaydev.com/gateway.do' : 'https://openapi.alipay.com/gateway.do';
        $bizContent = json_encode([
            'out_trade_no' => $order['order_no'],
            'total_amount' => number_format($order['amount'], 2, '.', ''),
            'subject' => 'ChatHub 续费 - 订单 ' . $order['order_no'],
            'product_code' => 'FAST_INSTANT_TRADE_PAY',
        ]);
        $params = [
            'app_id' => $cfg['alipay_app_id'],
            'method' => 'alipay.trade.page.pay',
            'charset' => 'utf-8',
            'sign_type' => 'RSA2',
            'timestamp' => date('Y-m-d H:i:s'),
            'version' => '1.0',
            'notify_url' => 'https://hub.275763.xyz/addons/chathub/index/payNotify/pay_method/alipay',
            'return_url' => 'https://hub.275763.xyz/addons/chathub/index/payReturn/order/' . $order['order_no'],
            'biz_content' => $bizContent,
        ];
        $params['sign'] = $this->_alipaySign($params, $cfg['alipay_merchant_private_key']);
        $url = $gateway . '?' . http_build_query($params);
        header('Location: ' . $url);
        exit;
    }

    private function _alipaySign($params, $privateKey)
    {
        ksort($params);
        $string = '';
        foreach ($params as $k => $v) {
            if ($k === 'sign' || $v === '') continue;
            $string .= '&' . $k . '=' . $v;
        }
        $string = substr($string, 1);
        $res = openssl_pkey_get_private($privateKey);
        openssl_sign($string, $sign, $res, OPENSSL_ALGO_SHA256);
        return base64_encode($sign);
    }

    public function payWechat()
    {
        $orderNo = $this->request->get('order');
        $order = Db::name('chathub_order')->where('order_no', $orderNo)->find();
        if (!$order) { exit('订单不存在'); }
        $cfg = get_addon_config('chathub');
        if (empty($cfg['wechat_enabled'])) { exit('微信支付未启用'); }
        if (empty($cfg['wechat_app_id']) || empty($cfg['wechat_mch_id']) || empty($cfg['wechat_api_v3_key'])) {
            exit('微信支付未配置完成，请在后台填写 APPID/商户号/APIv3密钥');
        }
        Db::name('chathub_order')->where('id', $order['id'])->update(['pay_method' => 'wechat', 'updatetime' => time()]);
        $codeUrl = $this->_wechatNativePay($order, $cfg);
        $cfg2 = get_addon_config('chathub');
        $siteName = $cfg2['site_name'] ?? 'ChatHub';
        $amount = number_format($order['amount'], 2);
        $qrUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=' . urlencode($codeUrl);
        $html = <<<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>微信支付 - SITENAME</title>
<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}.card{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:40px;max-width:420px;width:100%;text-align:center}h1{color:#fff;font-size:22px;margin-bottom:8px}.sub{color:#94a3b8;font-size:14px;margin-bottom:24px}.qr{background:#fff;padding:16px;border-radius:12px;display:inline-block;margin:16px 0}.amount{color:#07c160;font-size:32px;font-weight:700;margin:16px 0}.tip{color:#94a3b8;font-size:13px;margin-top:20px;line-height:1.6}.back{display:inline-block;margin-top:20px;color:#94a3b8;font-size:13px;text-decoration:none}.back:hover{color:#fff}</style>
</head>
<body>
<div class="card">
<h1>微信支付</h1>
<p class="sub">订单 ORDERNO</p>
<div class="qr"><img src="QRURL" width="240" height="240" alt="二维码"></div>
<div class="amount">¥AMOUNT</div>
<p class="tip">使用微信扫描二维码完成支付<br>支付完成后页面会自动跳转</p>
<a href="/addons/chathub/index/my" class="back">← 返回会员中心</a>
</div>
<script>
setTimeout(function(){location.reload()},5000);
</script>
</body></html>
HTML;
        $html = str_replace('SITENAME', $siteName, $html);
        $html = str_replace('ORDERNO', $orderNo, $html);
        $html = str_replace('QRURL', $qrUrl, $html);
        $html = str_replace('AMOUNT', $amount, $html);
        $this->render($html);
    }

    private function _wechatNativePay($order, $cfg)
    {
        $url = 'https://api.mch.weixin.qq.com/v3/pay/transactions/native';
        $body = json_encode([
            'appid' => $cfg['wechat_app_id'],
            'mchid' => $cfg['wechat_mch_id'],
            'description' => 'ChatHub 续费',
            'out_trade_no' => $order['order_no'],
            'notify_url' => 'https://hub.275763.xyz/addons/chathub/index/payNotify/pay_method/wechat',
            'amount' => ['total' => (int)($order['amount'] * 100), 'currency' => 'CNY'],
        ]);
        $token = $this->_wechatSign('POST', preg_replace('#https?://#', '', $url), $body, $cfg);
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true, CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Authorization: WECHATTOKEN_TYPE ' . $token],
            CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 30,
        ]);
        $resp = curl_exec($ch);
        $data = json_decode($resp, true);
        return $data['code_url'] ?? ('weixin://wxpay/bizpayurl?pr=CONFIGURE_ERROR_' . $order['order_no']);
    }

    private function _wechatSign($method, $url, $body, $cfg)
    {
        $random = bin2hex(random_bytes(16));
        $timestamp = (string)time();
        $nonce = bin2hex(random_bytes(8));
        $message = $method . "\n" . $url . "\n" . $timestamp . "\n" . $nonce . "\n" . $body . "\n";
        openssl_sign('sha256', $message, $sign, $cfg['wechat_key_path'], OPENSSL_ALGO_SHA256);
        $token = sprintf('mchid="%s",nonce_str="%s",timestamp="%s",serial_no="%s",signature="%s"',
            $cfg['wechat_mch_id'], $nonce, $timestamp, 'PLACEHOLDER_SERIAL', base64_encode($sign));
        return $token;
    }

    public function payNotify()
    {
        $method = $this->request->param('pay_method');
        $raw = file_get_contents('php://input');
        Db::name('chathub_log')->insert([
            'tenant_id' => 0, 'action' => 'pay_notify_' . $method,
            'detail' => $raw, 'status' => 'success', 'operator' => 'system', 'createtime' => time(),
        ]);
        if ($method === 'alipay') {
            $params = $this->request->post();
            $cfg = get_addon_config('chathub');
            $sign = $params['sign'] ?? '';
            unset($params['sign'], $params['sign_type']);
            ksort($params);
            $string = '';
            foreach ($params as $k => $v) { $string .= '&' . $k . '=' . '"' . $v . '"'; }
            $string = substr($string, 1);
            $res = openssl_pkey_get_public($cfg['alipay_public_key']);
            $verified = openssl_verify($string, base64_decode($sign), $res, OPENSSL_ALGO_SHA256);
            if ($verified === 1 && $params['trade_status'] === 'TRADE_SUCCESS') {
                $this->_markOrderPaid($params['out_trade_no'], 'alipay', $params['trade_no']);
                exit('success');
            }
            exit('fail');
        } elseif ($method === 'wechat') {
            $data = json_decode($raw, true);
            if (isset($data['out_trade_no'])) {
                $this->_markOrderPaid($data['out_trade_no'], 'wechat', $data['transaction_id'] ?? '');
                exit(json_encode(['code' => 'SUCCESS', 'message' => '成功']));
            }
        }
        exit('fail');
    }

    private function _markOrderPaid($orderNo, $method, $tradeNo)
    {
        $order = Db::name('chathub_order')->where('order_no', $orderNo)->find();
        if (!$order || $order['status'] === 'paid') return;
        Db::name('chathub_order')->where('id', $order['id'])->update([
            'status' => 'paid', 'pay_trade_no' => $tradeNo,
            'paid_at' => date('Y-m-d H:i:s'), 'updatetime' => time(),
        ]);
        $tenant = Db::name('chathub_tenant')->where('id', $order['tenant_id'])->find();
        if ($tenant) {
            $newExpire = max(strtotime($tenant['expire_at'] ?: 'now'), time());
            $newExpireAt = date('Y-m-d H:i:s', $newExpire + 30 * 86400);
            $logMsg = "续费成功，订单 {$orderNo}，金额 ¥{$order['amount']}";

            if (empty($tenant['embed_code'])) {
                Db::name('chathub_tenant')->where('id', $tenant['id'])->update([
                    'status' => 'provisioning',
                    'expire_at' => $newExpireAt,
                ]);
                $logMsg .= '（含资源开通）';
                $this->_provisionAsync($tenant['id']);
            } else {
                Db::name('chathub_tenant')->where('id', $tenant['id'])->update([
                    'status' => 'active',
                    'expire_at' => $newExpireAt,
                ]);
            }

            Db::name('chathub_log')->insert([
                'tenant_id' => $tenant['id'], 'action' => 'renew',
                'detail' => $logMsg,
                'status' => 'success', 'operator' => 'payment', 'createtime' => time(),
            ]);
        }
    }

    private function _provisionAsync($tenantId)
    {
        $tenant = Db::name('chathub_tenant')->where('id', $tenantId)->find();
        if (!$tenant) return false;

        $cfg = get_addon_config('chathub');
        $key = 'reprov-' . $tenant['id'] . '-' . md5($tenant['domain'] . '|' . $tenant['channel_type']);
        $provisionUrl = rtrim($cfg['provision_server_url'] ?? 'http://CoPaw:5566', '/') . '/provision';
        $payload = json_encode([
            'name' => $tenant['tenant_name'],
            'domain' => $tenant['domain'],
            'email' => $tenant['email'],
            'type' => $tenant['channel_type'],
            'max_agents' => (int)$tenant['max_agents'],
        ]);

        $ch = curl_init($provisionUrl);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'X-API-Key: ' . ($cfg['provision_api_key'] ?? 'chathub-default-key-change-me'),
                'Idempotency-Key: ' . $key,
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_CONNECTTIMEOUT => 5,
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $err = curl_error($ch);
        curl_close($ch);

        if ($err || $httpCode != 200) {
            Db::name('chathub_log')->insert([
                'tenant_id' => $tenantId, 'action' => 'reprovision',
                'detail' => "重试 provision 失败: " . ($err ?: "HTTP $httpCode"),
                'status' => 'failed', 'operator' => 'system', 'createtime' => time(),
            ]);
            return false;
        }

        $resultData = json_decode($response, true);
        if ($resultData && isset($resultData['inbox_id'])) {
            Db::name('chathub_tenant')->where('id', $tenantId)->update([
                'status' => 'active',
                'provisioned_at' => date('Y-m-d H:i:s'),
                'inbox_id' => $resultData['inbox_id'] ?? null,
                'inbox_token' => $resultData['inbox_token'] ?? null,
                'embed_code' => $resultData['embed_code'] ?? null,
                'agent_name' => $resultData['inbox_name'] ?? null,
                'team_id' => $resultData['team_id'] ?? null,
                'agent_cw_id' => $resultData['agent_cw_id'] ?? null,
                'agent_cw_password' => $resultData['agent_cw_password'] ?? null,
            ]);
            Db::name('chathub_log')->insert([
                'tenant_id' => $tenantId, 'action' => 'reprovision',
                'detail' => '补建资源成功 (inbox_id=' . ($resultData['inbox_id'] ?? '?') . ')',
                'status' => 'success', 'operator' => 'system', 'createtime' => time(),
            ]);
            return true;
        }

        Db::name('chathub_log')->insert([
            'tenant_id' => $tenantId, 'action' => 'reprovision',
            'detail' => '响应无效: ' . substr((string)$response, 0, 200),
            'status' => 'failed', 'operator' => 'system', 'createtime' => time(),
        ]);
        return false;
    }

    public function reprovision()
    {
        $userId = session('chathub_user_id');
        if (!$userId) {
            header('Location: /addons/chathub/index/login');
            exit;
        }
        $ids = $this->request->param('ids');
        if (!$ids) {
            header('Location: /addons/chathub/index/my?error=' . urlencode('缺少租户 ID'));
            exit;
        }
        $tenant = Db::name('chathub_tenant')->where('id', $ids)
            ->where('user_id', $userId)->find();
        if (!$tenant) {
            header('Location: /addons/chathub/index/my?error=' . urlencode('租户不存在或无权操作'));
            exit;
        }

        Db::name('chathub_tenant')->where('id', $tenant['id'])->update(['status' => 'provisioning']);
        $ok = $this->_provisionAsync($tenant['id']);
        $param = $ok ? 'just_paid=1' : 'provisioning=1';
        header('Location: /addons/chathub/index/my?' . $param);
        exit;
    }

    public function payReturn()
    {
        $orderNo = $this->request->param('order');
        $redirect = '/addons/chathub/index/my?order=' . urlencode($orderNo);
        $order = Db::name('chathub_order')->where('order_no', $orderNo)->find();
        if ($order) {
            $tenant = Db::name('chathub_tenant')->where('id', $order['tenant_id'])->find();
            if ($order['status'] !== 'paid') {
                $redirect .= '&pending=1';
            } elseif ($tenant && empty($tenant['embed_code'])) {
                $redirect .= '&provisioning=1';
            } else {
                $redirect .= '&just_paid=1';
            }
        }
        header('Location: ' . $redirect);
        exit;
    }
}
// touched at Fri Jun  5 10:07:55 AM CST 2026
