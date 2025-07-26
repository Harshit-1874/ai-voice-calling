#!/usr/bin/env python3
"""
Test script to demonstrate context-aware calling functionality
"""

import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.context_service import ContextService
from services.prisma_service import PrismaService

async def test_context_service():
    """Test the context service with sample transcription data"""
    
    print("🔧 Testing Context Service...")
    
    # Sample transcription data (like the one you provided)
    sample_call_history = [
        {
            "id": 1,
            "callSid": "CA1234567890",
            "startTime": "2025-07-21T21:28:00",
            "transcriptions": [
                {"speaker": "user", "text": "Maybe I'll see that video somewhere, I'm not waiting.", "timestamp": "2025-07-21T21:28:43.532307", "is_final": True},
                {"speaker": "assistant", "text": "Hi, this is Teya UK. We help businesses like yours accept payments easily and affordably. I'd love to know, what kind of business do you run?", "timestamp": "2025-07-21T21:28:44.148831", "is_final": True},
                {"speaker": "user", "text": "Hello", "timestamp": "2025-07-21T21:29:03.853287", "is_final": True},
                {"speaker": "assistant", "text": "Hello! This is Teya UK. We specialize in providing smart payment solutions for businesses. Can I ask what type of business you operate?", "timestamp": "2025-07-21T21:29:05.902179", "is_final": True},
                {"speaker": "user", "text": "I operate a full-time sous-chef line.", "timestamp": "2025-07-21T21:29:16.874139", "is_final": True},
                {"speaker": "assistant", "text": "A full-time shoe supplier, that's fantastic! We can definitely help you streamline your payment processes. How are you currently handling payments from your customers?", "timestamp": "2025-07-21T21:29:18.017152", "is_final": True},
                {"speaker": "user", "text": "I prefer only cached.", "timestamp": "2025-07-21T21:29:30.810399", "is_final": True},
                {"speaker": "assistant", "text": "I see, cash is straightforward, but it can limit some sales opportunities. With Teya, you could expand by accepting card and digital payments. Have you considered offering more payment options?", "timestamp": "2025-07-21T21:29:33.232633", "is_final": True},
                {"speaker": "user", "text": "No.", "timestamp": "2025-07-21T21:29:45.439093", "is_final": True},
                {"speaker": "assistant", "text": "Well, expanding payment options could attract more customers to your shoe business. With Teya, you can easily start accepting cards and mobile payments. Do you think being able to offer more payment methods would help your business grow?", "timestamp": "2025-07-21T21:29:47.670441", "is_final": True},
                {"speaker": "user", "text": "I don't want to explore any other options right now.", "timestamp": "2025-07-21T21:30:04.790792", "is_final": True},
                {"speaker": "user", "text": "I think I'm good with what I have.", "timestamp": "2025-07-21T21:30:06.470426", "is_final": True},
                {"speaker": "assistant", "text": "I understand, sticking with what works for you is important. If you ever decide to explore new payment options or need assistance in the future, Teya is here to help. Thanks for your time!", "timestamp": "2025-07-21T21:30:08.344029", "is_final": True}
            ]
        }
    ]
    
    context_service = ContextService()
    
    # Extract context from the call history
    context = context_service.extract_context_from_call_history(sample_call_history)
    
    print("📊 Extracted Context:")
    print(f"  👤 Customer Name: {context.get('customer_name', 'Not found')}")
    print(f"  🏢 Business Type: {context.get('business_type', 'Not found')}")
    print(f"  💳 Payment Preferences: {context.get('payment_preferences', [])}")
    print(f"  ❌ Previous Objections: {context.get('previous_objections', [])}")
    print(f"  💡 Key Insights: {context.get('key_insights', [])}")
    print(f"  📞 Total Calls: {context.get('total_calls', 0)}")
    
    # Generate context-aware system message
    base_system_message = "You are a professional sales representative for Teya UK."
    context_aware_message = context_service.generate_context_system_message(context, base_system_message)
    
    print("\n🤖 Context-Aware System Message:")
    print("=" * 80)
    print(context_aware_message)
    print("=" * 80)

async def test_database_context():
    """Test getting context from database (if available)"""
    
    print("\n🗄️ Testing Database Context...")
    
    prisma_service = PrismaService()
    
    try:
        async with prisma_service:
            # Try to get context for a sample phone number
            test_phone = "+1234567890"
            context = await prisma_service.get_contact_context_by_phone(test_phone)
            
            if context:
                print(f"✅ Found context for {test_phone}")
                print(f"  📞 Previous calls: {len(context.get('call_history', []))}")
                if context.get('contact'):
                    print(f"  👤 Contact: {context['contact'].get('name', 'Unknown')}")
            else:
                print(f"ℹ️ No context found for {test_phone} (this is expected for new numbers)")
                
    except Exception as e:
        print(f"⚠️ Database connection failed: {str(e)}")
        print("ℹ️ This is expected if the database is not running")

async def main():
    """Main test function"""
    print("🚀 Context-Aware Calling System Test")
    print("=" * 50)
    
    await test_context_service()
    await test_database_context()
    
    print("\n✅ Test completed!")
    print("\n📋 How to use the context-aware system:")
    print("1. Use GET /call/{phone_number}/context to check previous call history")
    print("2. Use POST /call/{phone_number} to initiate a context-aware call")
    print("3. The AI will automatically reference previous conversations")

if __name__ == "__main__":
    asyncio.run(main())
