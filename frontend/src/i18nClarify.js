// Customer-portal text for the automatic explanation level
// (backend/services/clarification_service.py). The two button labels are
// sent as the customer's message, so each must be a phrase the backend
// recognises in that language. Machine-assisted; review with native speakers.
export const CLARIFY_TEXT = {
  en: {
    btnNotUnderstood: "I didn't understand", btnTellMore: 'Tell me more',
    noteSimpler: "I'll explain that more simply.", noteReexplain: 'Let me explain it another way, with an example.', noteMore: 'Here is more detail.',
  },
  hi: {
    btnNotUnderstood: 'मुझे समझ नहीं आया', btnTellMore: 'और बताइए',
    noteSimpler: 'इसे और आसान भाषा में समझाते हैं।', noteReexplain: 'इसे एक उदाहरण के साथ दूसरे तरीके से समझाते हैं।', noteMore: 'यह रही और जानकारी।',
  },
  mr: {
    btnNotUnderstood: 'मला समजले नाही', btnTellMore: 'अजून सांगा',
    noteSimpler: 'हे आणखी सोप्या भाषेत समजावून सांगूया.', noteReexplain: 'एका उदाहरणासह वेगळ्या पद्धतीने समजावून सांगूया.', noteMore: 'ही अधिक माहिती.',
  },
  kn: {
    btnNotUnderstood: 'ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ', btnTellMore: 'ಇನ್ನಷ್ಟು ಹೇಳಿ',
    noteSimpler: 'ಇದನ್ನು ಇನ್ನಷ್ಟು ಸರಳವಾಗಿ ವಿವರಿಸುತ್ತೇನೆ.', noteReexplain: 'ಒಂದು ಉದಾಹರಣೆಯೊಂದಿಗೆ ಬೇರೆ ರೀತಿಯಲ್ಲಿ ವಿವರಿಸುತ್ತೇನೆ.', noteMore: 'ಇಲ್ಲಿ ಹೆಚ್ಚಿನ ಮಾಹಿತಿ ಇದೆ.',
  },
  te: {
    btnNotUnderstood: 'నాకు అర్థం కాలేదు', btnTellMore: 'ఇంకా చెప్పండి',
    noteSimpler: 'దీన్ని ఇంకా సులభంగా వివరిస్తాను.', noteReexplain: 'ఒక ఉదాహరణతో వేరే విధంగా వివరిస్తాను.', noteMore: 'ఇదిగో మరింత సమాచారం.',
  },
}
