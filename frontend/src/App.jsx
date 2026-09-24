import { useState } from 'react'
import { ArrowLeft, Building2, Circle, FileText, Headphones, Landmark, LayoutDashboard, LogOut, Mic, ShieldCheck, Sparkles, Users } from 'lucide-react'
import LoginPage from './components/LoginPage.jsx'
import LanguageSelect from './components/LanguageSelect.jsx'
import CustomerPanel from './components/CustomerPanel.jsx'
import CustomerPortal from './components/CustomerPortal.jsx'
import CopilotPanel from './components/CopilotPanel.jsx'
import SessionSummary from './components/SessionSummary.jsx'
import QueuePanel from './components/QueuePanel.jsx'
import SchemeUpdatesPanel from './components/SchemeUpdatesPanel.jsx'
import { apiFetch, getToken, getStaffName, clearSession } from './api.js'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'session', label: 'Customer Session', icon: Mic },
  { id: 'copilot', label: 'AI Copilot', icon: Sparkles },
  { id: 'queue', label: 'Queue', icon: Users },
  { id: 'summary', label: 'Summary', icon: FileText },
  { id: 'schemes', label: 'Schemes', icon: Landmark },
]

export default function App() {
  const [portal, setPortal] = useState(null)
  if (portal === 'customer') return <CustomerPortal onBack={() => setPortal(null)} />
  if (portal === 'staff') return <StaffPortal onExit={() => setPortal(null)} />
  return <PortalChooser onChoose={setPortal} />
}

function PortalChooser({ onChoose }) {
  return <div className="min-h-screen flex items-center justify-center px-5 py-10"><div className="w-full max-w-5xl"><div className="text-center mb-9"><div className="h-16 w-16 mx-auto rounded-2xl bg-primary-500 flex items-center justify-center shadow-card"><Headphones className="h-8 w-8 text-white" /></div><h1 className="mt-5 text-4xl sm:text-5xl font-display font-semibold text-primary-900">BoloBank</h1><p className="mt-3 text-lg text-charcoal/60">Multilingual, voice-first banking assistance for customers and staff</p></div><div className="grid md:grid-cols-2 gap-6"><button onClick={()=>onChoose('customer')} className="premium-card p-8 text-left hover:-translate-y-1 transition-transform group"><div className="h-14 w-14 rounded-2xl bg-primary-100 flex items-center justify-center"><Headphones className="h-7 w-7 text-primary-700" /></div><h2 className="mt-6 text-2xl font-display font-bold text-primary-900">Customer Portal</h2><p className="mt-2 text-charcoal/60">A simple, fully localized voice interface for customers in Marathi, Hindi, Kannada, Telugu or English.</p><span className="mt-6 inline-flex items-center gap-2 font-bold text-primary-700">Continue as customer →</span></button><button onClick={()=>onChoose('staff')} className="premium-card p-8 text-left hover:-translate-y-1 transition-transform group"><div className="h-14 w-14 rounded-2xl bg-secondary-100 flex items-center justify-center"><Building2 className="h-7 w-7 text-secondary-600" /></div><h2 className="mt-6 text-2xl font-display font-bold text-primary-900">Staff Portal</h2><p className="mt-2 text-charcoal/60">An authenticated employee workspace with queue management, bilingual transcripts, AI Copilot and session summaries.</p><span className="mt-6 inline-flex items-center gap-2 font-bold text-secondary-600">Continue as bank staff →</span></button></div><p className="mt-7 text-center text-sm text-charcoal/45 flex items-center justify-center gap-2"><ShieldCheck className="h-4 w-4" />Customer and staff experiences are separated by design.</p></div></div>
}

function StaffPortal({ onExit }) {
  const [staffName, setStaffName] = useState(getToken() ? getStaffName() : null)
  const [tab, setTab] = useState('dashboard')
  const [language, setLanguage] = useState('mr')
  const [sessionId, setSessionId] = useState(null)
  const [summary, setSummary] = useState(null)

  if (!staffName) return <div><button onClick={onExit} className="fixed top-5 left-5 z-50 p-3 rounded-full bg-white shadow-soft"><ArrowLeft className="h-5 w-5" /></button><LoginPage onLoggedIn={(name)=>setStaffName(name||'Staff')} /></div>

  const logout=()=>{clearSession();setStaffName(null);setSessionId(null);setSummary(null);setTab('dashboard')}
  const startSession=async()=>{const form=new FormData();form.append('language',language);const res=await apiFetch('/sessions/start',{method:'POST',body:form});const data=await res.json();setSessionId(data.session_id);setTab('session')}
  const endSession=async()=>{const res=await apiFetch(`/sessions/${sessionId}/summary`);if(res.ok)setSummary(await res.json());setTab('summary')}

  return <div className="min-h-screen"><StaffHeader tab={tab} setTab={setTab} sessionActive={!!sessionId} staffName={staffName} onLogout={logout} onExit={onExit}/><main className="max-w-7xl mx-auto px-5 sm:px-7 py-8 sm:py-10 animate-fadeUp">{tab==='dashboard'&&<StaffDashboard language={language} setLanguage={setLanguage} onStart={startSession} sessionId={sessionId}/>} {tab==='session'&&sessionId&&<CustomerPanel sessionId={sessionId} language={language} onEndSession={endSession}/>} {tab==='session'&&!sessionId&&<EmptyState message="Start a staff-assisted customer session from the Dashboard first." icon={Mic}/>} {tab==='copilot'&&<CopilotPanel/>} {tab==='queue'&&<QueuePanel/>} {tab==='schemes'&&<SchemeUpdatesPanel/>} {tab==='summary'&&(summary?<SessionSummary summary={summary} onStartNew={()=>{setSessionId(null);setSummary(null);setTab('dashboard')}}/>:<EmptyState message="End a staff-assisted session to see its summary here." icon={FileText}/>)}</main><footer className="max-w-7xl mx-auto px-6 pb-8 text-center text-sm text-charcoal/40">BoloBank Staff Portal · AI assists, employees decide</footer></div>
}

function StaffHeader({tab,setTab,sessionActive,staffName,onLogout,onExit}) { return <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-xl border-b border-primary-100"><div className="max-w-7xl mx-auto px-5 sm:px-7 py-3.5 flex items-center justify-between gap-4"><div className="flex items-center gap-3"><button onClick={onExit} className="p-2 rounded-full hover:bg-primary-50"><ArrowLeft className="h-5 w-5" /></button><div className="h-10 w-10 rounded-xl bg-secondary-100 flex items-center justify-center"><Building2 className="h-5 w-5 text-secondary-600" /></div><div><p className="font-display font-bold text-lg text-primary-900">BoloBank Staff</p><p className="text-xs text-charcoal/50">Employee workspace</p></div></div><nav className="hidden 2xl:flex gap-1 bg-primary-50/80 border border-primary-100 rounded-full p-1">{TABS.map(t=>{const Icon=t.icon;const active=tab===t.id;return <button key={t.id} onClick={()=>setTab(t.id)} className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-semibold whitespace-nowrap ${active?'bg-white text-primary-900 shadow-soft':'text-charcoal/60 hover:bg-white'}`}><Icon className="h-4 w-4" />{t.label}</button>})}</nav><div className="hidden md:flex items-center gap-3"><span className={`inline-flex items-center gap-2 text-sm font-semibold px-3 py-1.5 rounded-full border ${sessionActive?'bg-secondary-50 text-secondary-600 border-secondary-400/50':'bg-primary-50 text-charcoal/45 border-primary-100'}`}><Circle className={`h-2 w-2 ${sessionActive?'fill-secondary-600':'fill-charcoal/30'}`}/>{sessionActive?'Session active':'No active session'}</span><span className="text-sm text-charcoal/55">{staffName}</span><button onClick={onLogout} className="p-2 rounded-full hover:bg-primary-50"><LogOut className="h-4 w-4" /></button></div></div><nav className="2xl:hidden flex gap-1 px-4 pb-3 overflow-x-auto">{TABS.map(t=>{const Icon=t.icon;return <button key={t.id} onClick={()=>setTab(t.id)} className={`flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-semibold whitespace-nowrap ${tab===t.id?'bg-primary-500 text-white':'bg-primary-50 text-charcoal/60'}`}><Icon className="h-3.5 w-3.5" />{t.label}</button>})}</nav></header> }

function StaffDashboard({language,setLanguage,onStart,sessionId}) { return <div className="grid lg:grid-cols-5 gap-8 items-start"><div className="lg:col-span-2"><span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-secondary-600 bg-secondary-50 px-3 py-1.5 rounded-full mb-4"><Building2 className="h-3.5 w-3.5"/>Staff-only workspace</span><h1 className="text-4xl sm:text-5xl font-display font-semibold text-primary-900 mb-4 leading-tight">Employee dashboard</h1><p className="text-charcoal/70 text-lg">Manage assisted sessions, view bilingual transcripts, use the AI Copilot and handle customer queues without exposing staff controls to customers.</p><div className="mt-6 rounded-2xl border border-primary-100 bg-white/70 p-5"><p className="font-bold text-charcoal">Clear role separation</p><p className="text-sm text-charcoal/60 mt-1">Customers use a separate fully localized portal. This dashboard remains operational and staff-focused.</p></div></div><div className="lg:col-span-3 premium-card p-7 sm:p-9"><LanguageSelect value={language} onChange={setLanguage}/><button onClick={onStart} className="mt-8 w-full py-4 rounded-2xl bg-primary-500 text-white font-display font-semibold text-lg hover:bg-primary-600">{sessionId?'Start another assisted session':'Start assisted customer session'}</button></div></div> }

function EmptyState({message,icon:Icon}) { return <div className="max-w-md mx-auto text-center py-24"><div className="mx-auto mb-5 h-16 w-16 rounded-2xl bg-primary-100 flex items-center justify-center"><Icon className="h-7 w-7 text-primary-600" /></div><p className="text-charcoal/60 text-lg">{message}</p></div> }
