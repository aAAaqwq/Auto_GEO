// AutoGEO Cookie Sync - Background Service Worker
// 自动同步：chrome.cookies.onChanged + chrome.alarms 轮询后端同步请求

const DEBUG = true;
function log(msg, ...a) { if (DEBUG) console.log(`[AutoGEO] ${msg}`, ...a); }

const PLATFORM_CONFIG = {
  doubao:   { domains: ['doubao.com','bytedance.com'],        loginCookies: ['sessionid','uid_tt','odin_tt','sid_guard','multi_sids'] },
  deepseek: { domains: ['deepseek.com'],                       loginCookies: [] },
  qianwen:  { domains: ['qianwen.com','tongyi.aliyun.com'],   loginCookies: ['tongyi_sso_ticket','tongyi_sso_ticket_hash','login_aliyunid'] },
};

async function getBackendUrl() {
  const r = await chrome.storage.local.get(['backendUrl']);
  return r.backendUrl || 'http://127.0.0.1:8001';
}

// ==================== Cookie 获取 ====================
async function getAllCookies(platformId) {
  const cfg = PLATFORM_CONFIG[platformId];
  if (!cfg) return [];
  const all = []; const seen = new Set();
  for (const d of cfg.domains) {
    for (const p of ['.'+d, d]) {
      try {
        for (const c of await chrome.cookies.getAll({domain:p})) {
          const k = c.name+'|'+c.domain;
          if (!seen.has(k)) { seen.add(k); all.push(c); }
        }
      } catch(e) {}
    }
  }
  return all.map(c=>({name:c.name,value:c.value,domain:c.domain,path:c.path,expires:c.expirationDate,httpOnly:c.httpOnly,secure:c.secure,sameSite:c.sameSite}));
}

// ==================== 指纹 ====================
function fingerprint() {
  let s={w:1920,h:1080}; try{s.w=self.screen?.width||1920;s.h=self.screen?.height||1080}catch(e){}
  let p='Win32'; try{p=navigator.platform||'Win32'}catch(e){}
  let l=['zh-CN','en']; try{l=navigator.languages||['zh-CN']}catch(e){}
  return {user_agent:navigator.userAgent,platform:p,language:navigator.language||'zh-CN',languages:l,hardware_concurrency:navigator.hardwareConcurrency||8,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,screen:s,viewport:s};
}

// ==================== 同步 ====================
async function syncPlatform(platformId) {
  const url = await getBackendUrl();
  const cookies = await getAllCookies(platformId);
  if (!cookies.length) { log(platformId+': 无cookie'); return null; }
  const unique=[]; const seen=new Set();
  for(const c of cookies){const k=c.name+'|'+c.domain;if(!seen.has(k)){seen.add(k);unique.push(c);}}

  const ctrl=new AbortController(); const t=setTimeout(()=>ctrl.abort(),10000);
  try {
    const r=await fetch(`${url}/api/auth/sync-cookies`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:1,project_id:1,platform:platformId,cookies:unique,local_storage:{},fingerprint:fingerprint()}),signal:ctrl.signal});
    clearTimeout(t);
    return await r.json();
  }catch(e){clearTimeout(t);log('sync fail: '+e.message);return null;}
}

// ==================== 自动同步：cookie 变化 ====================
const pending={};
function isLoginCookie(pid,name){const c=PLATFORM_CONFIG[pid];return c?c.loginCookies.some(n=>name.toLowerCase()===n.toLowerCase()):false;}
function detectPlatform(domain){for(const[pid,cfg]of Object.entries(PLATFORM_CONFIG))for(const d of cfg.domains)if(domain.includes(d))return pid;return null;}

chrome.cookies.onChanged.addListener(({cookie,cause,removed})=>{
  if(removed||cause!=='explicit'&&cause!=='overwrite')return;
  const pid=detectPlatform(cookie.domain);
  if(!pid||!isLoginCookie(pid,cookie.name))return;
  log(`检测登录cookie: ${cookie.name} (${pid})`);
  if(pending[pid])clearTimeout(pending[pid]);
  pending[pid]=setTimeout(async()=>{delete pending[pid];await syncPlatform(pid);},3000);
});

// ==================== 轮询后端同步请求（前端"刷新状态"触发） ====================
let lastPoll=0;
async function pollSyncRequests(){
  const url=await getBackendUrl();
  try{
    const r=await fetch(`${url}/api/auth/sync-requests?since=${lastPoll}`,{signal:AbortSignal.timeout(5000)});
    if(!r.ok)return;
    const data=await r.json();
    if(data.sync_all||data.platforms?.length>0){
      log('收到同步请求:',data);
      const platforms=data.sync_all?Object.keys(PLATFORM_CONFIG):data.platforms||[];
      for(const p of platforms) await syncPlatform(p);
    }
    lastPoll=Date.now();
  }catch(e){/* ignore */}
}

// 每 5 秒轮询一次
chrome.alarms.create('pollSync',{periodInMinutes:5/60});
chrome.alarms.onAlarm.addListener((alarm)=>{
  if(alarm.name==='pollSync')pollSyncRequests();
});

// 启动时也轮询一次
pollSyncRequests();

// ==================== 消息处理 ====================
chrome.runtime.onMessage.addListener((msg,sender,sendResponse)=>{
  if(msg.action==='syncCookies'){syncPlatform(msg.platform).then(r=>sendResponse(r));return true;}
  if(msg.action==='getAllCookies'){getAllCookies(msg.platform).then(r=>sendResponse(r));return true;}
});
chrome.runtime.onMessageExternal?.addListener?.((msg,sender,sendResponse)=>{
  if(msg.action==='syncAllPlatforms'){
    Promise.all(Object.keys(PLATFORM_CONFIG).map(p=>syncPlatform(p).catch(()=>null)))
      .then(r=>sendResponse({success:true,count:r.filter(x=>x&&x.success).length}));
    return true;
  }
});

// ==================== 注册扩展ID ====================
async function registerId(){
  const url=await getBackendUrl();
  try{await fetch(`${url}/api/auth/register-extension`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({extension_id:chrome.runtime.id})});log('ID注册: '+chrome.runtime.id);}catch(e){}
}

log('SW启动, ID:'+chrome.runtime.id);
getBackendUrl().then(u=>{log('后端:'+u);registerId();});
chrome.runtime.onStartup?.addListener?.(registerId);
