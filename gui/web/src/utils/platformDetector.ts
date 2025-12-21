export const detectPlatform = (packageName: string): string => {
  const pkg = packageName.toLowerCase()
  if (pkg.includes('huawei')) return '华为'
  if (pkg.includes('miui') || pkg.includes('xiaomi')) return '小米'
  if (pkg.includes('oppo') || pkg.includes('coloros')) return 'OPPO'
  if (pkg.includes('vivo') || pkg.includes('funtouch')) return 'vivo'
  if (pkg.includes('samsung')) return '三星'
  if (pkg.includes('tencent')) return '腾讯'
  if (pkg.includes('qihoo')) return '360'
  if (pkg.includes('baidu')) return '百度'
  if (pkg.includes('wandoujia')) return '豌豆荚'
  if (pkg.includes('yingyonghui')) return '应用汇'
  if (pkg.startsWith('com.android.') && !pkg.includes('huawei') && !pkg.includes('miui')) return 'Android'
  return '其他'
}

export const availablePlatforms = ['华为', '小米', 'OPPO', 'vivo', '三星', 'Android', '腾讯', '360', '百度', '豌豆荚', '应用汇', '其他']

