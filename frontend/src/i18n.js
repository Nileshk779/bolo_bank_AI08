import { ELIGIBILITY_TEXT } from './i18nEligibility.js'

export const LANGUAGES = [
  { code: 'mr', label: 'मराठी', english: 'Marathi' },
  { code: 'hi', label: 'हिंदी', english: 'Hindi' },
  { code: 'kn', label: 'ಕನ್ನಡ', english: 'Kannada' },
  { code: 'te', label: 'తెలుగు', english: 'Telugu' },
  { code: 'en', label: 'English', english: 'English' },
]

const M = {
  en: {
    appName: 'BoloBank', customerPortal: 'Customer Portal', staffPortal: 'Staff Portal',
    customerSubtitle: 'Simple voice banking in your language', staffSubtitle: 'Secure workspace for bank staff',
    choosePortal: 'How would you like to continue?', customerCard: 'I am a Customer', customerCardDesc: 'Use voice assistance in your preferred language',
    staffCard: 'I am Bank Staff', staffCardDesc: 'Open the staff dashboard, queue and AI Copilot',
    chooseLanguage: 'Choose your preferred language', continue: 'Continue', changeLanguage: 'Change language',
    welcome: 'Welcome to BoloBank', welcomeText: 'Speak naturally. BoloBank will guide you step by step.',
    startSession: 'Start voice assistance', endSession: 'End session', holdToSpeak: 'Hold to speak',
    listening: 'Listening… release to send', transcribing: 'Understanding your voice…', thinking: 'Finding the right information…', speaking: 'Speaking the reply…',
    listenAgain: 'Listen again', yes: 'Yes', no: 'No', elderlyMode: 'Elderly Voice Mode', on: 'On', off: 'Off',
    yourConversation: 'Your conversation', noConversation: 'Your conversation will appear here.',
    you: 'You', assistant: 'BoloBank', secureScreen: 'Shown securely on screen — not spoken aloud',
    helpStaff: 'Need a staff member?', helpStaffDesc: 'Ask for human assistance at any time.', requestHelp: 'Request human help',
    sessionEnded: 'Your session has ended', thankYou: 'Thank you for using BoloBank.', newSession: 'Start another session',
    microphoneBlocked: 'Microphone permission is required. Please allow microphone access.',
    recordingFailed: 'We could not understand the recording. Please try again.',
    aiFailed: 'We could not reach the assistance service. Please ask a staff member for help.',
    back: 'Back', privacy: 'Your sensitive banking information is protected and is never spoken aloud.', secureValue: 'Secure account information',
  },
  hi: {
    appName: 'बोलोबैंक', customerPortal: 'ग्राहक पोर्टल', staffPortal: 'स्टाफ पोर्टल',
    customerSubtitle: 'आपकी भाषा में सरल वॉइस बैंकिंग', staffSubtitle: 'बैंक कर्मचारियों के लिए सुरक्षित कार्यक्षेत्र',
    choosePortal: 'आप कैसे आगे बढ़ना चाहते हैं?', customerCard: 'मैं ग्राहक हूँ', customerCardDesc: 'अपनी पसंदीदा भाषा में वॉइस सहायता लें',
    staffCard: 'मैं बैंक स्टाफ हूँ', staffCardDesc: 'स्टाफ डैशबोर्ड, कतार और AI कोपायलट खोलें',
    chooseLanguage: 'अपनी पसंदीदा भाषा चुनें', continue: 'आगे बढ़ें', changeLanguage: 'भाषा बदलें',
    welcome: 'बोलोबैंक में आपका स्वागत है', welcomeText: 'स्वाभाविक रूप से बोलें। बोलोबैंक आपको चरण-दर-चरण मार्गदर्शन देगा।',
    startSession: 'वॉइस सहायता शुरू करें', endSession: 'सत्र समाप्त करें', holdToSpeak: 'बोलने के लिए दबाकर रखें',
    listening: 'सुन रहा हूँ… भेजने के लिए छोड़ें', transcribing: 'आपकी आवाज़ समझ रहे हैं…', thinking: 'सही जानकारी खोज रहे हैं…', speaking: 'उत्तर सुनाया जा रहा है…',
    listenAgain: 'फिर से सुनें', yes: 'हाँ', no: 'नहीं', elderlyMode: 'वरिष्ठ नागरिक वॉइस मोड', on: 'चालू', off: 'बंद',
    yourConversation: 'आपकी बातचीत', noConversation: 'आपकी बातचीत यहाँ दिखाई देगी।',
    you: 'आप', assistant: 'बोलोबैंक', secureScreen: 'सुरक्षित रूप से स्क्रीन पर दिखाया गया — आवाज़ में नहीं बोला जाएगा',
    helpStaff: 'स्टाफ की मदद चाहिए?', helpStaffDesc: 'आप किसी भी समय कर्मचारी की सहायता मांग सकते हैं।', requestHelp: 'मानव सहायता मांगें',
    sessionEnded: 'आपका सत्र समाप्त हो गया है', thankYou: 'बोलोबैंक का उपयोग करने के लिए धन्यवाद।', newSession: 'नया सत्र शुरू करें',
    microphoneBlocked: 'माइक्रोफोन की अनुमति आवश्यक है। कृपया माइक्रोफोन की अनुमति दें।', recordingFailed: 'रिकॉर्डिंग समझ नहीं आई। कृपया फिर प्रयास करें।',
    aiFailed: 'सहायता सेवा उपलब्ध नहीं है। कृपया बैंक कर्मचारी से मदद लें।', back: 'वापस', privacy: 'आपकी संवेदनशील बैंकिंग जानकारी सुरक्षित है और उसे आवाज़ में नहीं बोला जाता।', secureValue: 'सुरक्षित खाता जानकारी',
  },
  mr: {
    appName: 'बोलोबँक', customerPortal: 'ग्राहक पोर्टल', staffPortal: 'कर्मचारी पोर्टल',
    customerSubtitle: 'तुमच्या भाषेत सोपी व्हॉइस बँकिंग', staffSubtitle: 'बँक कर्मचाऱ्यांसाठी सुरक्षित कार्यक्षेत्र',
    choosePortal: 'तुम्हाला कसे पुढे जायचे आहे?', customerCard: 'मी ग्राहक आहे', customerCardDesc: 'तुमच्या पसंतीच्या भाषेत व्हॉइस सहाय्य वापरा',
    staffCard: 'मी बँक कर्मचारी आहे', staffCardDesc: 'कर्मचारी डॅशबोर्ड, रांग आणि AI कोपायलट उघडा',
    chooseLanguage: 'तुमची पसंतीची भाषा निवडा', continue: 'पुढे जा', changeLanguage: 'भाषा बदला',
    welcome: 'बोलोबँकमध्ये आपले स्वागत आहे', welcomeText: 'नैसर्गिकपणे बोला. बोलोबँक तुम्हाला टप्प्याटप्प्याने मार्गदर्शन करेल.',
    startSession: 'व्हॉइस सहाय्य सुरू करा', endSession: 'सत्र समाप्त करा', holdToSpeak: 'बोलण्यासाठी दाबून ठेवा',
    listening: 'ऐकत आहे… पाठवण्यासाठी सोडा', transcribing: 'तुमचा आवाज समजून घेत आहोत…', thinking: 'योग्य माहिती शोधत आहोत…', speaking: 'उत्तर ऐकवले जात आहे…',
    listenAgain: 'पुन्हा ऐका', yes: 'हो', no: 'नाही', elderlyMode: 'ज्येष्ठ नागरिक व्हॉइस मोड', on: 'चालू', off: 'बंद',
    yourConversation: 'तुमचे संभाषण', noConversation: 'तुमचे संभाषण येथे दिसेल.',
    you: 'तुम्ही', assistant: 'बोलोबँक', secureScreen: 'सुरक्षितपणे स्क्रीनवर दाखवले आहे — मोठ्याने बोलले जाणार नाही',
    helpStaff: 'कर्मचाऱ्याची मदत हवी आहे?', helpStaffDesc: 'तुम्ही कधीही मानवी सहाय्य मागू शकता.', requestHelp: 'मानवी मदत मागा',
    sessionEnded: 'तुमचे सत्र समाप्त झाले आहे', thankYou: 'बोलोबँक वापरल्याबद्दल धन्यवाद.', newSession: 'नवीन सत्र सुरू करा',
    microphoneBlocked: 'मायक्रोफोनची परवानगी आवश्यक आहे. कृपया मायक्रोफोन वापरण्याची परवानगी द्या.', recordingFailed: 'रेकॉर्डिंग समजू शकले नाही. कृपया पुन्हा प्रयत्न करा.',
    aiFailed: 'सहाय्य सेवा उपलब्ध नाही. कृपया बँक कर्मचाऱ्याची मदत घ्या.', back: 'मागे', privacy: 'तुमची संवेदनशील बँकिंग माहिती सुरक्षित आहे आणि ती मोठ्याने बोलली जात नाही.', secureValue: 'सुरक्षित खाते माहिती',
  },
  kn: {
    appName: 'ಬೋಲೋಬ್ಯಾಂಕ್', customerPortal: 'ಗ್ರಾಹಕ ಪೋರ್ಟಲ್', staffPortal: 'ಸಿಬ್ಬಂದಿ ಪೋರ್ಟಲ್',
    customerSubtitle: 'ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ ಸರಳ ಧ್ವನಿ ಬ್ಯಾಂಕಿಂಗ್', staffSubtitle: 'ಬ್ಯಾಂಕ್ ಸಿಬ್ಬಂದಿಗೆ ಸುರಕ್ಷಿತ ಕಾರ್ಯಕ್ಷೇತ್ರ',
    choosePortal: 'ನೀವು ಹೇಗೆ ಮುಂದುವರಿಯಲು ಬಯಸುತ್ತೀರಿ?', customerCard: 'ನಾನು ಗ್ರಾಹಕ', customerCardDesc: 'ನಿಮ್ಮ ಇಷ್ಟದ ಭಾಷೆಯಲ್ಲಿ ಧ್ವನಿ ಸಹಾಯ ಬಳಸಿ',
    staffCard: 'ನಾನು ಬ್ಯಾಂಕ್ ಸಿಬ್ಬಂದಿ', staffCardDesc: 'ಸಿಬ್ಬಂದಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್, ಸರತಿ ಮತ್ತು AI ಕೋಪೈಲಟ್ ತೆರೆಯಿರಿ',
    chooseLanguage: 'ನಿಮ್ಮ ಇಷ್ಟದ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ', continue: 'ಮುಂದುವರಿಸಿ', changeLanguage: 'ಭಾಷೆ ಬದಲಿಸಿ',
    welcome: 'ಬೋಲೋಬ್ಯಾಂಕ್‌ಗೆ ಸ್ವಾಗತ', welcomeText: 'ಸ್ವಾಭಾವಿಕವಾಗಿ ಮಾತನಾಡಿ. ಬೋಲೋಬ್ಯಾಂಕ್ ಹಂತ ಹಂತವಾಗಿ ಮಾರ್ಗದರ್ಶನ ನೀಡುತ್ತದೆ.',
    startSession: 'ಧ್ವನಿ ಸಹಾಯ ಆರಂಭಿಸಿ', endSession: 'ಸೆಷನ್ ಮುಗಿಸಿ', holdToSpeak: 'ಮಾತನಾಡಲು ಒತ್ತಿಹಿಡಿಯಿರಿ',
    listening: 'ಕೇಳುತ್ತಿದ್ದೇವೆ… ಕಳುಹಿಸಲು ಬಿಡಿ', transcribing: 'ನಿಮ್ಮ ಧ್ವನಿಯನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತಿದ್ದೇವೆ…', thinking: 'ಸರಿಯಾದ ಮಾಹಿತಿಯನ್ನು ಹುಡುಕುತ್ತಿದ್ದೇವೆ…', speaking: 'ಉತ್ತರವನ್ನು ಓದುತ್ತಿದ್ದೇವೆ…',
    listenAgain: 'ಮತ್ತೆ ಕೇಳಿ', yes: 'ಹೌದು', no: 'ಇಲ್ಲ', elderlyMode: 'ಹಿರಿಯ ನಾಗರಿಕ ಧ್ವನಿ ಮೋಡ್', on: 'ಆನ್', off: 'ಆಫ್',
    yourConversation: 'ನಿಮ್ಮ ಸಂಭಾಷಣೆ', noConversation: 'ನಿಮ್ಮ ಸಂಭಾಷಣೆ ಇಲ್ಲಿ ಕಾಣಿಸುತ್ತದೆ.', you: 'ನೀವು', assistant: 'ಬೋಲೋಬ್ಯಾಂಕ್',
    secureScreen: 'ಸುರಕ್ಷಿತವಾಗಿ ಪರದೆಯಲ್ಲಿ ತೋರಿಸಲಾಗಿದೆ — ಜೋರಾಗಿ ಓದಲಾಗುವುದಿಲ್ಲ', helpStaff: 'ಸಿಬ್ಬಂದಿಯ ಸಹಾಯ ಬೇಕೆ?', helpStaffDesc: 'ಯಾವಾಗ ಬೇಕಾದರೂ ಮಾನವ ಸಹಾಯ ಕೇಳಬಹುದು.', requestHelp: 'ಮಾನವ ಸಹಾಯ ಕೇಳಿ',
    sessionEnded: 'ನಿಮ್ಮ ಸೆಷನ್ ಮುಗಿದಿದೆ', thankYou: 'ಬೋಲೋಬ್ಯಾಂಕ್ ಬಳಸಿದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು.', newSession: 'ಹೊಸ ಸೆಷನ್ ಆರಂಭಿಸಿ',
    microphoneBlocked: 'ಮೈಕ್ರೋಫೋನ್ ಅನುಮತಿ ಅಗತ್ಯವಿದೆ. ದಯವಿಟ್ಟು ಅನುಮತಿಸಿ.', recordingFailed: 'ರೆಕಾರ್ಡಿಂಗ್ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', aiFailed: 'ಸಹಾಯ ಸೇವೆ ಲಭ್ಯವಿಲ್ಲ. ಸಿಬ್ಬಂದಿಯಿಂದ ಸಹಾಯ ಪಡೆಯಿರಿ.', back: 'ಹಿಂದೆ', privacy: 'ನಿಮ್ಮ ಸೂಕ್ಷ್ಮ ಬ್ಯಾಂಕಿಂಗ್ ಮಾಹಿತಿ ಸುರಕ್ಷಿತವಾಗಿದೆ ಮತ್ತು ಜೋರಾಗಿ ಓದಲಾಗುವುದಿಲ್ಲ.', secureValue: 'ಸುರಕ್ಷಿತ ಖಾತೆ ಮಾಹಿತಿ',
  },
  te: {
    appName: 'బోలోబ్యాంక్', customerPortal: 'కస్టమర్ పోర్టల్', staffPortal: 'స్టాఫ్ పోర్టల్',
    customerSubtitle: 'మీ భాషలో సులభమైన వాయిస్ బ్యాంకింగ్', staffSubtitle: 'బ్యాంక్ సిబ్బందికి సురక్షిత కార్యస్థలం',
    choosePortal: 'మీరు ఎలా కొనసాగాలనుకుంటున్నారు?', customerCard: 'నేను కస్టమర్‌ని', customerCardDesc: 'మీకు నచ్చిన భాషలో వాయిస్ సహాయం ఉపయోగించండి',
    staffCard: 'నేను బ్యాంక్ స్టాఫ్‌ని', staffCardDesc: 'స్టాఫ్ డ్యాష్‌బోర్డ్, క్యూ మరియు AI కోపైలట్ తెరవండి',
    chooseLanguage: 'మీకు నచ్చిన భాషను ఎంచుకోండి', continue: 'కొనసాగండి', changeLanguage: 'భాష మార్చండి',
    welcome: 'బోలోబ్యాంక్‌కు స్వాగతం', welcomeText: 'సహజంగా మాట్లాడండి. బోలోబ్యాంక్ మిమ్మల్ని దశలవారీగా మార్గనిర్దేశం చేస్తుంది.',
    startSession: 'వాయిస్ సహాయం ప్రారంభించండి', endSession: 'సెషన్ ముగించండి', holdToSpeak: 'మాట్లాడటానికి నొక్కి పట్టుకోండి',
    listening: 'వింటున్నాం… పంపడానికి విడిచేయండి', transcribing: 'మీ వాయిస్‌ను అర్థం చేసుకుంటున్నాం…', thinking: 'సరైన సమాచారాన్ని వెతుకుతున్నాం…', speaking: 'సమాధానం వినిపిస్తోంది…',
    listenAgain: 'మళ్లీ వినండి', yes: 'అవును', no: 'కాదు', elderlyMode: 'వృద్ధుల వాయిస్ మోడ్', on: 'ఆన్', off: 'ఆఫ్',
    yourConversation: 'మీ సంభాషణ', noConversation: 'మీ సంభాషణ ఇక్కడ కనిపిస్తుంది.', you: 'మీరు', assistant: 'బోలోబ్యాంక్',
    secureScreen: 'సురక్షితంగా స్క్రీన్‌పై చూపించబడింది — గట్టిగా చదవబడదు', helpStaff: 'సిబ్బంది సహాయం కావాలా?', helpStaffDesc: 'ఎప్పుడైనా మానవ సహాయం కోరవచ్చు.', requestHelp: 'మానవ సహాయం కోరండి',
    sessionEnded: 'మీ సెషన్ ముగిసింది', thankYou: 'బోలోబ్యాంక్ ఉపయోగించినందుకు ధన్యవాదాలు.', newSession: 'కొత్త సెషన్ ప్రారంభించండి',
    microphoneBlocked: 'మైక్రోఫోన్ అనుమతి అవసరం. దయచేసి అనుమతించండి.', recordingFailed: 'రికార్డింగ్ అర్థం కాలేదు. మళ్లీ ప్రయత్నించండి.', aiFailed: 'సహాయ సేవ అందుబాటులో లేదు. సిబ్బంది సహాయం తీసుకోండి.', back: 'వెనక్కి', privacy: 'మీ సున్నితమైన బ్యాంకింగ్ సమాచారం సురక్షితం మరియు గట్టిగా చదవబడదు.', secureValue: 'సురక్షిత ఖాతా సమాచారం',
  },
}

for (const [lang, strings] of Object.entries(ELIGIBILITY_TEXT)) Object.assign(M[lang], strings)

export function t(language, key) {
  return M[language]?.[key] ?? M.en[key] ?? key
}

/** t() with {placeholder} substitution, e.g. tf('mr', 'resSpoken', { count: 3 }). */
export function tf(language, key, params = {}) {
  return t(language, key).replace(/\{(\w+)\}/g, (_, name) => (params[name] ?? `{${name}}`))
}
