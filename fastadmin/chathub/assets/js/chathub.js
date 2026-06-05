/**
 * ChatHub 租户管理 JavaScript
 */
define(['jquery', 'bootstrap', 'template'], function ($, Bootstrap, Template) {
    var Controller = {
        index: function () {
            // 初始化表格
            Controller.api.initTable();
            
            // 绑定事件
            Controller.api.bindEvents();
        },
        
        add: function () {
            // 初始化表单
            Controller.api.initForm();
        },
        
        edit: function () {
            // 初始化表单
            Controller.api.initForm();
            
            // 填充数据
            Controller.api.fillFormData();
        },
        
        dashboard: function () {
            // 初始化仪表盘
            Controller.api.initDashboard();
        },
        
        api: {
            // 初始化表格
            initTable: function () {
                // 加载租户列表
                Controller.api.loadTenants();
                
                // 绑定筛选事件
                $('.filter-select, .filter-input').on('change', function () {
                    Controller.api.loadTenants(1);
                });
            },
            
            // 加载租户列表
            loadTenants: function (page) {
                page = page || 1;
                
                $.ajax({
                    url: Fast.api.fixurl('chathub/index/index'),
                    type: 'GET',
                    data: {
                        page: page,
                        filter: JSON.stringify(Controller.api.getFilters())
                    },
                    success: function (res) {
                        if (res.rows && res.rows.length > 0) {
                            Controller.api.renderTenants(res.rows);
                            Controller.api.renderPagination(res.total, page);
                            $('#empty-state').hide();
                            $('.table-container table').show();
                            $('.pagination-wrapper').show();
                        } else {
                            $('#empty-state').show();
                            $('.table-container table').hide();
                            $('.pagination-wrapper').hide();
                        }
                    }
                });
            },
            
            // 获取筛选条件
            getFilters: function () {
                return {
                    status: $('.filter-select').eq(0).val(),
                    channel_type: $('.filter-select').eq(1).val(),
                    search: $('.filter-input').val()
                };
            },
            
            // 渲染租户列表
            renderTenants: function (tenants) {
                var html = '';
                tenants.forEach(function (tenant) {
                    var statusClass = 'status-' + tenant.status;
                    var channelIcon = tenant.channel_type === 'web_widget' ? 'fa-globe' : 'fa-code';
                    var channelText = tenant.channel_type_text || (tenant.channel_type === 'web_widget' ? '网页组件' : 'API接口');
                    
                    html += '<tr>';
                    html += '<td>';
                    html += '  <div class="tenant-info">';
                    html += '    <div class="tenant-avatar">' + tenant.tenant_name.charAt(0).toUpperCase() + '</div>';
                    html += '    <div class="tenant-details">';
                    html += '      <h4>' + tenant.tenant_name + '</h4>';
                    html += '      <p>' + (tenant.agent_name || '未配置') + '</p>';
                    html += '    </div>';
                    html += '  </div>';
                    html += '</td>';
                    html += '<td>' + tenant.domain + '</td>';
                    html += '<td><span class="channel-tag"><i class="fa ' + channelIcon + '"></i> ' + channelText + '</span></td>';
                    html += '<td><span class="status-badge ' + statusClass + '">' + tenant.status_text + '</span></td>';
                    html += '<td>' + (tenant.provisioned_at || '-') + '</td>';
                    html += '<td>';
                    html += '  <div class="action-buttons">';
                    html += '    <a href="' + Fast.api.fixurl('chathub/index/edit/ids/' + tenant.id) + '" class="action-btn action-btn-edit" title="编辑"><i class="fa fa-pencil"></i></a>';
                    if (tenant.status !== 'active') {
                        html += '    <button class="action-btn action-btn-provision" title="开通" onclick="Controller.api.provisionTenant(' + tenant.id + ')"><i class="fa fa-rocket"></i></button>';
                    }
                    html += '    <button class="action-btn action-btn-delete" title="删除" onclick="Controller.api.deleteTenant(' + tenant.id + ')"><i class="fa fa-trash"></i></button>';
                    html += '  </div>';
                    html += '</td>';
                    html += '</tr>';
                });
                $('#tenant-list').html(html);
            },
            
            // 渲染分页
            renderPagination: function (total, currentPage) {
                var pageSize = 10;
                var totalPages = Math.ceil(total / pageSize);
                var html = '';
                
                if (currentPage > 1) {
                    html += '<span class="page-link" onclick="Controller.api.loadTenants(' + (currentPage - 1) + ')">上一页</span>';
                }
                
                for (var i = 1; i <= totalPages; i++) {
                    if (i === currentPage) {
                        html += '<span class="page-link active">' + i + '</span>';
                    } else {
                        html += '<span class="page-link" onclick="Controller.api.loadTenants(' + i + ')">' + i + '</span>';
                    }
                }
                
                if (currentPage < totalPages) {
                    html += '<span class="page-link" onclick="Controller.api.loadTenants(' + (currentPage + 1) + ')">下一页</span>';
                }
                
                $('#pagination').html(html);
                $('#pagination-info').text('显示 ' + ((currentPage-1)*pageSize+1) + '-' + Math.min(currentPage*pageSize, total) + ' 条，共 ' + total + ' 条');
            },
            
            // 开通租户
            provisionTenant: function (id) {
                if (confirm('确定要开通这个租户吗？')) {
                    Fast.api.ajax({
                        url: Fast.api.fixurl('chathub/index/provision/ids/' + id),
                        type: 'POST'
                    }, function (res) {
                        Controller.api.loadTenants();
                    });
                }
            },
            
            // 删除租户
            deleteTenant: function (id) {
                if (confirm('确定要删除这个租户吗？此操作不可恢复。')) {
                    Fast.api.ajax({
                        url: Fast.api.fixurl('chathub/index/del/ids/' + id),
                        type: 'POST'
                    }, function (res) {
                        Controller.api.loadTenants();
                    });
                }
            },
            
            // 初始化表单
            initForm: function () {
                // 通道类型选择
                $('.channel-option').click(function () {
                    $('.channel-option').removeClass('active');
                    $(this).addClass('active');
                    $('input[name="row[channel_type]"]').val($(this).data('value'));
                });
                
                // 表单提交
                $('#tenant-form').on('submit', function (e) {
                    e.preventDefault();
                    
                    var formData = $(this).serialize();
                    var url = $(this).attr('action');
                    
                    $.ajax({
                        url: url,
                        type: 'POST',
                        data: formData,
                        success: function (res) {
                            if (res.code === 1) {
                                Fast.api.msg('操作成功！');
                                setTimeout(function () {
                                    location.href = Fast.api.fixurl('chathub/index/index');
                                }, 1000);
                            } else {
                                Fast.api.msg(res.msg || '操作失败', 'danger');
                            }
                        },
                        error: function () {
                            Fast.api.msg('网络错误，请重试', 'danger');
                        }
                    });
                });
            },
            
            // 填充表单数据
            fillFormData: function () {
                // 从页面获取数据并填充
                var row = window.rowData || {};
                
                if (row.tenant_name) {
                    $('input[name="row[tenant_name]"]').val(row.tenant_name);
                }
                if (row.domain) {
                    $('input[name="row[domain]"]').val(row.domain);
                }
                if (row.agent_name) {
                    $('input[name="row[agent_name]"]').val(row.agent_name);
                }
                if (row.status) {
                    $('select[name="row[status]"]').val(row.status);
                }
                if (row.channel_type) {
                    $('.channel-option').removeClass('active');
                    $('.channel-option[data-value="' + row.channel_type + '"]').addClass('active');
                    $('input[name="row[channel_type]"]').val(row.channel_type);
                }
            },
            
            // 初始化仪表盘
            initDashboard: function () {
                // 添加动画效果
                $('.stat-card').each(function (index) {
                    $(this).css({
                        'opacity': '0',
                        'transform': 'translateY(20px)',
                        'animation': 'fadeInUp 0.5s ease forwards',
                        'animation-delay': (index * 0.1) + 's'
                    });
                });
            },
            
            // 绑定事件
            bindEvents: function () {
                // 刷新按钮
                $(document).on('click', '.btn-refresh', function () {
                    Controller.api.loadTenants();
                });
            }
        }
    };
    
    return Controller;
});
