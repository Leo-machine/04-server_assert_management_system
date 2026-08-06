/** 配件品类（与后端 category_specs.PART_CATEGORIES 对齐） */
export const PART_CATEGORIES = [
  '内存',
  '机械硬盘',
  '固态硬盘',
  'RAID卡',
  '光模块',
  '网卡',
  'HBA卡',
  '算力卡',
]

export const SERVER_CATEGORY = '服务器'
export const ALL_MANAGED_CATEGORIES = [...PART_CATEGORIES, SERVER_CATEGORY]

export const RESPONSIBLE_GROUPS = ['基础组', '运营组', '网络组', '平台组']

export const SCRAP_REASONS = ['本单位销毁', '返厂换新']
