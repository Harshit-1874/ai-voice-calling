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
            'service': ['service', 'repair', 'maintenance', 'cleaning', 'plumbing', 'electrical']
        }

    def extract_context_from_call_history(self, call_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract useful context from previous call transcriptions"""
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
        
        # Analyze all transcriptions
        all_transcripts = []
        for call in sorted_calls:
            transcriptions = call.get('transcriptions', [])
            if transcriptions:
                all_transcripts.extend(transcriptions)
        
        if all_transcripts:
            context.update(self._analyze_transcripts(all_transcripts))
        
        # Get conversation summaries
        for call in sorted_calls:
            conversation = call.get('conversation')
            if conversation and conversation.get('summary'):
                if not context['last_conversation_summary']:
                    context['last_conversation_summary'] = conversation['summary']
                
                if conversation.get('nextAction'):
                    context['call_outcomes'].append(conversation['nextAction'])
        
        return context

    def _analyze_transcripts(self, transcripts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze transcript entries to extract insights"""
        context = {}
        user_texts = []
        assistant_texts = []
        
        # Separate user and assistant messages
        for entry in transcripts:
            if entry.get('speaker') == 'user' and entry.get('is_final', True):
                user_texts.append(entry.get('text', '').lower())
            elif entry.get('speaker') == 'assistant' and entry.get('is_final', True):
                assistant_texts.append(entry.get('text', '').lower())
        
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
        
        # Check if customer was busy
        busy_indicators = ['busy', 'meeting', 'can\'t talk', 'call back', 'later']
        for text in user_texts:
            for indicator in busy_indicators:
                if indicator in text:
                    insights.append("Customer was busy during last call")
                    break
        
        # Check conversation flow
        if len(user_texts) > 5:
            insights.append("Had a detailed conversation previously")
        
        return insights

    def generate_context_system_message(self, context: Dict[str, Any], base_system_message: str) -> str:
        """Generate a context-aware system message for the AI"""
        if not context or context.get('total_calls', 0) == 0:
            return base_system_message
        
        context_additions = []
        
        # Add customer name context
        if context.get('customer_name'):
            context_additions.append(f"The customer's name is {context['customer_name']}. Greet them by name and reference that you've spoken before.")
        
        # Add business context
        if context.get('business_name'):
            context_additions.append(f"They run a business called {context['business_name']}.")
        elif context.get('business_type'):
            context_additions.append(f"They operate in the {context['business_type']} industry.")
        
        # Add previous conversation context
        if context.get('last_conversation_summary'):
            context_additions.append(f"Previous conversation summary: {context['last_conversation_summary']}")
        
        # Add call outcome context
        if context.get('call_outcomes'):
            latest_outcome = context['call_outcomes'][0]
            context_additions.append(f"Last call outcome: {latest_outcome}")
        
        # Add objections context
        if context.get('previous_objections'):
            objections = ', '.join(context['previous_objections'][:2])
            context_additions.append(f"Previous concerns raised: {objections}")
        
        # Add payment preferences
        if context.get('payment_preferences'):
            prefs = ', '.join(context['payment_preferences'])
            context_additions.append(f"Payment preferences mentioned: {prefs}")
        
        # Add insights
        if context.get('key_insights'):
            insights = '. '.join(context['key_insights'])
            context_additions.append(f"Key insights: {insights}")
        
        # Add timing context
        if context.get('total_calls') > 1:
            context_additions.append(f"This is your {context['total_calls'] + 1} conversation with this customer.")
        
        if context_additions:
            context_text = "\n\nCONTEXT FROM PREVIOUS CALLS:\n" + "\n".join(f"- {addition}" for addition in context_additions)
            context_text += "\n\nUse this context to have a more personalized conversation. Reference previous discussions naturally and continue building the relationship."
            return base_system_message + context_text
        
        return base_system_message
