{
    'name': 'Volan Genclik',
    'version': '2.4.6',
    'summary': 'Badminton üçün tam idman idarəetmə sistemi',

    'author': 'Aim',
    'website': 'https://github.com/7aim/BadmintonOdoo',
    'category': 'Services/Sport Management',
    'license': 'LGPL-3',
    'images': [
        'static/description/icon.png',
    ],
    'depends': ['base', 'contacts', 'mail'],
    'data': [
        #'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/cron_jobs.xml',
        #'views/res_partner_views.xml',
        'views/sport_system_views.xml',
        'views/badminton_session_filter_views.xml',
        'views/badminton_session_views.xml',
        'views/badminton_sale_views.xml',
        'views/badminton_lesson_freeze_views.xml',
        'views/badminton_lesson_simple_views.xml',
        'views/badminton_group_views.xml',
        'views/customer_wizard_views.xml',
        'views/qr_scanner_views.xml',
        'views/session_extend_wizard_views.xml',
        'views/badminton_attendance_check_views.xml',
        'views/menu_views.xml',
        'views/cash_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'volan_genclikk/static/src/css/style.css',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
    'external_dependencies': {
        'python': ['qrcode', 'pillow'],
    },
    'web_icon': 'volan_genclikk/static/description/icon.png'
}
