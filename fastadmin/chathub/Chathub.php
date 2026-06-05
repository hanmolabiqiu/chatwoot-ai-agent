<?php
namespace addons\chathub;

use app\common\library\Menu;
use think\Addons;

class Chathub extends Addons
{
    protected $menu = [
        [
            'name' => 'chathub',
            'title' => 'ChatHub',
            'icon' => 'fa fa-headset',
            'ismenu' => 1,
            'weigh' => 1,
            'sublist' => [
                ["name" => "chathub/index/index", "title" => "租户列表"],
                ["name" => "chathub/index/dashboard", "title" => "控制面板"],
            ]
        ]
    ];

    public function install()
    {
        Menu::create($this->menu);
        return true;
    }

    public function uninstall()
    {
        Menu::delete("chathub");
        return true;
    }

    public function enable()
    {
        Menu::enable("chathub");
        return true;
    }

    public function disable()
    {
        Menu::disable("chathub");
        return true;
    }

    public function upgrade()
    {
        Menu::upgrade('chathub', $this->menu);
        return true;
    }

    /**
     * config_init 钩子
     */
    public function ConfigInit()
    {
        // nothing to init
    }

    /**
     * 兼容 fallback
     */
    public function run()
    {
        // nothing
    }
}
