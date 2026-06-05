<?php
namespace addons\chathub\model;

use think\Model;

class ChathubTenant extends Model
{
    // 表名
    protected $name = 'chathub_tenant';
    
    // 自动写入时间戳
    protected $autoWriteTimestamp = 'int';
    
    // 定义时间戳字段名
    protected $createTime = 'createtime';
    protected $updateTime = 'updatetime';
    
    // 追加属性
    protected $append = [
        'status_text',
        'channel_type_text',
        'team_id_text',
        'email_text'
    ];
    
    /**
     * 状态文本
     */
    public function getStatusTextAttr($value, $data)
    {
        $status = ['pending' => '待开通', 'active' => '正常', 'suspended' => '已暂停', 'disabled' => '已禁用'];
        return $status[$data['status']] ?? '';
    }
    
    /**
     * 通道类型文本
     */
    public function getChannelTypeTextAttr($value, $data)
    {
        $types = ['web_widget' => '网页组件', 'api' => 'API接口'];
        return $types[$data['channel_type']] ?? '';
    }
    
    /**
     * 配置JSON解析
     */
    public function getConfigAttr($value)
    {
        return $value ? json_decode($value, true) : [];
    }
    
    public function setConfigAttr($value)
    {
        return json_encode($value);
    }
    
    /**
     * API凭据JSON解析
     */
    public function getApiCredentialsAttr($value)
    {
        return $value ? json_decode($value, true) : [];
    }
    
    public function setApiCredentialsAttr($value)
    {
        return json_encode($value);
    }
    
    /**
     * 团队ID文本
     */
    public function getTeamIdTextAttr($value, $data)
    {
        if (empty($data['team_id'])) {
            return '-';
        }
        return '#' . $data['team_id'];
    }

    /**
     * 邮箱文本（脱敏显示）
     */
    public function getEmailTextAttr($value, $data)
    {
        if (empty($data['email'])) {
            return '-';
        }
        $parts = explode('@', $data['email']);
        if (count($parts) === 2) {
            $name = $parts[0];
            $len = strlen($name);
            $masked = substr($name, 0, min(2, $len)) . str_repeat('*', max(0, $len - 2));
            return $masked . '@' . $parts[1];
        }
        return $data['email'];
    }
}
