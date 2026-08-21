import test from 'node:test'
import assert from 'node:assert/strict'

import { level2Categories, level2CategoriesForDomain, managedCategoriesForScopes, managedLeafCategoriesForScopes } from './assetScopes.js'

const tree = [
  {
    id: 1,
    name: '数字化类',
    enabled: true,
    children: [
      {
        id: 11,
        name: '服务器类',
        code: 'DIGITAL_SERVER',
        enabled: true,
        children: [
          { id: 111, name: '内存', enabled: true, business_category: '内存' },
          { id: 112, name: '已停用类型', enabled: false, business_category: '网卡' },
        ],
      },
    ],
  },
  {
    id: 2,
    name: '计量类',
    enabled: true,
    children: [
      {
        id: 21,
        name: '表计类',
        code: 'METERING_METER',
        enabled: true,
        children: [{ id: 211, name: '单相电能表', enabled: true, business_category: null }],
      },
    ],
  },
]

test('具体类型随当前专业和二级目录派生，不回退到固定全量类别', () => {
  const scopes = level2Categories(tree)
  const digital = scopes.filter((scope) => scope.domain === '数字化类')
  const metering = scopes.filter((scope) => scope.domain === '计量类')

  assert.deepEqual(managedCategoriesForScopes(digital), ['服务器', '内存'])
  assert.deepEqual(managedCategoriesForScopes(metering), [])
})

test('切换一级专业后只返回该专业下的二级设备类别', () => {
  assert.deepEqual(level2CategoriesForDomain(tree, '1').map((scope) => scope.name), ['服务器类'])
  assert.deepEqual(level2CategoriesForDomain(tree, '2').map((scope) => scope.name), ['表计类'])
})

test('停用的三级目录不会出现在品牌和型号的具体类型中', () => {
  const server = level2Categories(tree).find((scope) => scope.code === 'DIGITAL_SERVER')

  assert.equal(managedCategoriesForScopes([server]).includes('网卡'), false)
})

test('品牌三级类型不包含二级设备整机标记', () => {
  const server = level2Categories(tree).find((scope) => scope.code === 'DIGITAL_SERVER')

  assert.deepEqual(managedLeafCategoriesForScopes([server]), ['内存'])
  assert.equal(managedLeafCategoriesForScopes([server]).includes('服务器'), false)
})
