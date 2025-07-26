import logging
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ContextService:
    """Service to analyze call transcriptions and extract context for future calls"""
    
    def __init__(self):
        self.business_keywords = {
            'restaurant': ['restaurant', 'cafe', 'diner', 'food', 'kitchen', 'chef', 'cook', 'dining'],
            'retail': ['store', 'shop', 'retail', 'boutique', 'merchandise', 'sales'],
            'salon': ['salon', 'hair', 'beauty', 'spa', 'barber'],
            'medical': ['clinic', 'doctor', 'medical', 'health', 'dental', 'hospital'],
            'automotive': ['garage', 'car', 'auto', 'mechanic', 'vehicle'],
            'service': ['service', 'repair', 'maintenance', 'cleaning', 'plumbing', 'electrical'],
            'technology': ['web development', 'software', 'app development', 'tech', 'developer', 'programmer', 'coding', 'website', 'digital agency', 'it services', 'web design'],
            'agency': ['agency', 'marketing agency', 'advertising', 'creative agency', 'consulting']
        }

    def extract_context_from_call_history(self, call_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract useful context from previous call transcriptions and summaries"""
        context = {
            'customer_name': None,
            'business_name': None,
            'business_type': None,
            'previous_interests': [],
            'previous_objections': [],
            'call_outcomes': [],
            'last_conversation_summary': None,
            'total_calls': len(call_history),
            'last_call_date': None,
            'payment_preferences': [],
            'key_insights': []
        }
        
        if not call_history:
            return context
        
        # Sort by date (most recent first)
        sorted_calls = sorted(call_history, key=lambda x: x.get('startTime', ''), reverse=True)
        
        # Set last call date
        if sorted_calls:
            context['last_call_date'] = sorted_calls[0].get('startTime')
        
        # Extract insights from AI-generated call conclusions (much simpler than transcription parsing)
        conclusions = []
        for call in sorted_calls:
            # Check if there are transcriptions with conclusions
            transcriptions = call.get('transcriptions', [])
            for transcription in transcriptions:
                # Check for conclusion field directly (from updated schema)
                conclusion = transcription.get('conclusion')
                if conclusion:
                    conclusions.append(conclusion)
                    logger.info(f"Found conclusion for context: {conclusion[:100]}...")
        
        logger.info(f"Found {len(conclusions)} conclusions for context analysis")
        
        # Analyze conclusions using AI insights
        if conclusions:
            context.update(self._analyze_conclusions(conclusions))
        else:
            logger.info("No conclusions found, using basic context")
        
        # Get conversation summaries (fallback if no conclusions)
        for call in sorted_calls:
            conversation = call.get('conversation')
            if conversation and conversation.get('summary'):
                if not context['last_conversation_summary']:
                    context['last_conversation_summary'] = conversation['summary']
                
                if conversation.get('nextAction'):
                    context['call_outcomes'].append(conversation['nextAction'])
        
        return context

    def _analyze_conclusions(self, conclusions: List[str]) -> Dict[str, Any]:
        """Analyze AI-generated call conclusions to extract business insights (much simpler!)"""
        context = {}
        
        # Combine all conclusions into one text for analysis
        combined_text = " ".join(conclusions).lower()
        
        # Extract business type from conclusions using keywords
        context['business_type'] = self._extract_business_type_from_text(combined_text)
        
        # Extract key insights from the conclusions
        insights = []
        
        # Check for engagement patterns
        if any(word in combined_text for word in ['disengaged', 'abruptly', 'hung up', 'bye']):
            insights.append("Customer seemed disengaged in previous call")
        elif any(word in combined_text for word in ['interested', 'potential', 'follow-up']):
            insights.append("Customer showed interest in payment solutions")
        
        # Check for business information sharing
        if any(phrase in combined_text for phrase in ['business', 'payment processes', 'current payment']):
            insights.append("Business details already discussed in previous call")
        
        # Check for meeting/callback requests
        if any(phrase in combined_text for phrase in ['meeting', 'callback', 'follow up', 'contact later']):
            insights.append("Customer requested callback - was busy during last call")
        
        # Check for payment discussion
        if any(phrase in combined_text for phrase in ['payment solutions', 'payment processing', 'smart payment']):
            insights.append("Payment solutions discussion was initiated")
            
        # Extract interests and objections from conclusions
        if any(word in combined_text for word in ['genuine interest', 'interested', 'wants to learn']):
            context['previous_interests'] = ["Showed interest in payment solutions"]
        
        if any(word in combined_text for word in ['not interested', 'declined', 'rejected']):
            context['previous_objections'] = ["Previously declined services"]
        
        context['key_insights'] = insights
        
        return context

    def _extract_business_type_from_text(self, text: str) -> Optional[str]:
        """Extract business type from any text using keywords"""
        for business_type, keywords in self.business_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return business_type
        return None

    def _analyze_transcripts(self, transcripts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze transcript entries to extract insights"""
        context = {}
        user_texts = []
        assistant_texts = []
        
        # Separate user and assistant messages from the new format
        for entry in transcripts:
            speaker = entry.get('speaker', '').lower()
            text = entry.get('text', '').lower()
            is_final = entry.get('is_final', True)
            
            if is_final and text:  # Only process final, non-empty transcripts
                if speaker == 'user':
                    user_texts.append(text)
                elif speaker == 'assistant':
                    assistant_texts.append(text)
        
        # Extract customer name
        context['customer_name'] = self._extract_name(user_texts + assistant_texts)
        
        # Extract business information
        context['business_name'] = self._extract_business_name(user_texts)
        context['business_type'] = self._extract_business_type(user_texts)
        
        # Extract payment preferences
        context['payment_preferences'] = self._extract_payment_preferences(user_texts)
        
        # Extract interests and objections
        context['previous_interests'] = self._extract_interests(user_texts)
        context['previous_objections'] = self._extract_objections(user_texts)
        
        # Extract key insights
        context['key_insights'] = self._extract_key_insights(user_texts, assistant_texts)
        
        return context

    def _extract_name(self, texts: List[str]) -> Optional[str]:
        """Extract customer name from conversation"""
        name_patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"this is (\w+)",
            r"call me (\w+)",
            r"i am (\w+)"
        ]
        
        for text in texts:
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1).capitalize()
                    if len(name) > 2 and name.isalpha():  # Basic validation
                        return name
        return None

    def _extract_business_name(self, user_texts: List[str]) -> Optional[str]:
        """Extract business name from user responses"""
        business_patterns = [
            r"my business is (.+?)(?:\.|,|$)",
            r"we run (.+?)(?:\.|,|$)", 
            r"i own (.+?)(?:\.|,|$)",
            r"my company is (.+?)(?:\.|,|$)",
            r"it's called (.+?)(?:\.|,|$)"
        ]
        
        for text in user_texts:
            for pattern in business_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    business = match.group(1).strip()
                    if len(business) > 2 and len(business) < 50:
                        return business.title()
        return None

    def _extract_business_type(self, user_texts: List[str]) -> Optional[str]:
        """Extract type of business from conversation"""
        for text in user_texts:
            for business_type, keywords in self.business_keywords.items():
                for keyword in keywords:
                    if keyword in text:
                        return business_type
        return None

    def _extract_payment_preferences(self, user_texts: List[str]) -> List[str]:
        """Extract payment preferences mentioned"""
        preferences = []
        payment_keywords = {
            'cash': ['cash', 'cash only', 'prefer cash'],
            'card': ['card', 'credit card', 'debit card'],
            'digital': ['digital', 'mobile payment', 'app', 'contactless'],
            'check': ['check', 'cheque']
        }
        
        for text in user_texts:
            for payment_type, keywords in payment_keywords.items():
                for keyword in keywords:
                    if keyword in text and payment_type not in preferences:
                        preferences.append(payment_type)
        
        return preferences

    def _extract_interests(self, user_texts: List[str]) -> List[str]:
        """Extract things the customer showed interest in"""
        interests = []
        interest_indicators = [
            'interested', 'sounds good', 'tell me more', 'how does',
            'what about', 'i like', 'that sounds', 'yes'
        ]
        
        for text in user_texts:
            for indicator in interest_indicators:
                if indicator in text:
                    interests.append(text.strip())
                    break
        
        return interests[:3]  # Keep top 3

    def _extract_objections(self, user_texts: List[str]) -> List[str]:
        """Extract objections or concerns raised"""
        objections = []
        objection_indicators = [
            'not interested', 'don\'t want', 'don\'t need', 'no thanks',
            'not right now', 'too expensive', 'happy with', 'already have',
            'don\'t think', 'not sure', 'maybe later'
        ]
        
        for text in user_texts:
            for indicator in objection_indicators:
                if indicator in text:
                    objections.append(text.strip())
                    break
        
        return objections[:3]  # Keep top 3

    def _extract_key_insights(self, user_texts: List[str], assistant_texts: List[str]) -> List[str]:
        """Extract key insights from the conversation"""
        insights = []
        
        # Check if call was cut short
        if len(user_texts) < 3:
            insights.append("Previous call was very brief")
        
        # Check if customer was busy or requested callback
        busy_indicators = ['busy', 'meeting', 'can\'t talk', 'call back', 'later', 'call you later', 'not a good time']
        for text in user_texts:
            for indicator in busy_indicators:
                if indicator in text:
                    insights.append("Customer requested callback - was busy during last call")
                    break
        
        # Check conversation flow
        if len(user_texts) > 5:
            insights.append("Had a detailed conversation previously")
        
        # Check if business details were already shared
        business_details = ['business', 'company', 'operate', 'run', 'work', 'agency', 'development']
        business_mentioned = False
        for text in user_texts:
            for detail in business_details:
                if detail in text:
                    business_mentioned = True
                    break
        
        if business_mentioned:
            insights.append("Business details already discussed in previous call")
        
        # Check if payment discussion started
        payment_terms = ['payment', 'cash', 'card', 'transactions', 'digital', 'processing']
        payment_discussed = False
        for text in user_texts + assistant_texts:
            for term in payment_terms:
                if term in text:
                    payment_discussed = True
                    break
        
        if payment_discussed:
            insights.append("Payment solutions discussion was initiated")
        
        return insights

    def generate_context_system_message(self, context: Dict[str, Any], base_system_message: str) -> str:
        """Generate a context-aware system message for the AI"""
        if not context or context.get('total_calls', 0) == 0:
            return base_system_message
        
        context_additions = []
        
        # Build specific callback greeting based on previous conversation
        callback_context = self._build_callback_context(context)
        if callback_context:
            context_additions.append(f"CALLBACK CONTEXT: {callback_context}")
            context_additions.append("Start with: 'Hi, this is Teya UK calling back. I know you mentioned [reference their business/situation]. Is now a better time to continue our conversation?'")
        
        # Add customer name context
        if context.get('customer_name'):
            context_additions.append(f"The customer's name is {context['customer_name']}. Greet them by name.")
        
        # Add business context with specific details
        business_context = self._build_business_context(context)
        if business_context:
            context_additions.append(f"BUSINESS CONTEXT: {business_context}")
        
        # Add payment discussion context
        payment_context = self._build_payment_context(context)
        if payment_context:
            context_additions.append(f"PAYMENT CONTEXT: {payment_context}")
        
        # Add call outcome context
        if context.get('call_outcomes'):
            latest_outcome = context['call_outcomes'][0]
            context_additions.append(f"Previous call outcome: {latest_outcome}")
        
        # Add specific insights
        if context.get('key_insights'):
            for insight in context['key_insights']:
                if 'callback' in insight.lower() or 'busy' in insight.lower():
                    context_additions.append(f"IMPORTANT: {insight} - acknowledge this and pick up where you left off")
                else:
                    context_additions.append(f"Note: {insight}")
        
        # Add conversation continuation instructions
        if context.get('total_calls') > 1:
            context_additions.append(f"This is your {context['total_calls'] + 1} conversation with this customer. Continue building the relationship and don't repeat information already discussed.")
        
        if context_additions:
            context_text = "\n\nCONTEXT FROM PREVIOUS CALLS:\n" + "\n".join(f"- {addition}" for addition in context_additions)
            context_text += "\n\nIMPORTANT: Use this context to have a personalized conversation. Reference previous discussions naturally, acknowledge their specific situation, and continue from where you left off. Do NOT start with generic questions about their business if this information was already discussed."
            return base_system_message + context_text
        
        return base_system_message

    def _build_callback_context(self, context: Dict[str, Any]) -> str:
        """Build specific callback context for greetings"""
        insights = context.get('key_insights', [])
        for insight in insights:
            if 'callback' in insight.lower() or 'busy' in insight.lower():
                return "This is a callback - customer was busy and requested to be called back"
        return ""

    def _build_business_context(self, context: Dict[str, Any]) -> str:
        """Build business context summary"""
        business_info = []
        
        if context.get('business_name'):
            business_info.append(f"Business: {context['business_name']}")
        elif context.get('business_type'):
            business_info.append(f"Business type: {context['business_type']}")
        
        # Add specific business details from insights
        insights = context.get('key_insights', [])
        for insight in insights:
            if 'business details' in insight.lower():
                business_info.append("Business details already discussed")
        
        return ", ".join(business_info) if business_info else ""

    def _build_payment_context(self, context: Dict[str, Any]) -> str:
        """Build payment context summary"""
        payment_info = []
        
        if context.get('payment_preferences'):
            prefs = ', '.join(context['payment_preferences'])
            payment_info.append(f"Current payment methods: {prefs}")
        
        insights = context.get('key_insights', [])
        for insight in insights:
            if 'payment' in insight.lower():
                payment_info.append("Payment solutions discussion was started")
        
        return ", ".join(payment_info) if payment_info else ""
