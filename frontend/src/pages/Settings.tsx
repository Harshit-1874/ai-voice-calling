import { useState, useEffect } from 'react';

interface Settings {
  voice: string;
  systemPrompt: string;
  temperature: number;
}

const initialSettings: Settings = {
  voice: 'alloy',
  systemPrompt: 'You are a helpful AI assistant making phone calls. Be professional, friendly, and concise.',
  temperature: 0.7,
};

const VOICE_OPTIONS = [
  { value: 'alloy', label: 'Alloy' },
  { value: 'echo', label: 'Echo' },
  { value: 'fable', label: 'Fable' },
  { value: 'onyx', label: 'Onyx' },
  { value: 'nova', label: 'Nova' },
  { value: 'shimmer', label: 'Shimmer' },
];

export default function Settings() {
  const [settings, setSettings] = useState<Settings>(initialSettings);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Fetch settings on component mount
  useEffect(() => {
    const fetchSettings = async () => {
      setIsFetching(true);
      setFetchError(null);
      try {
        const response = await fetch('https://ai-voice-calling-3.onrender.com/constants');
        if (!response.ok) {
          throw new Error('Failed to fetch settings');
        }
        const data = await response.json();
        console.log('Fetched settings:', data);
        
        // Map the API response to our settings structure
        const fetchedSettings: Settings = {
          voice: data.VOICE || initialSettings.voice,
          systemPrompt: data.SYSTEM_MESSAGE || initialSettings.systemPrompt,
          temperature: data.TEMPERATURE !== undefined ? data.TEMPERATURE : initialSettings.temperature,
        };
        
        setSettings(fetchedSettings);
      } catch (error: any) {
        setFetchError(error.message || 'Failed to fetch settings');
        console.error('Error fetching settings:', error);
      } finally {
        setIsFetching(false);
      }
    };

    fetchSettings();
  }, []);

  const handleSaveSettings = async () => {
    setIsLoading(true);
    setSaveMessage(null);
    try {
      const response = await fetch('https://ai-voice-calling-3.onrender.com/constants/ai-configs', {
        method: 'POST', // or 'POST' depending on your API
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          VOICE: settings.voice,
          SYSTEM_MESSAGE: settings.systemPrompt, // API might expect snake_case
          TEMPERATURE: settings.temperature,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }

      setSaveMessage('Settings saved successfully');
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error: any) {
      setSaveMessage(error.message || 'Failed to save settings');
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSettings(prev => ({ ...prev, voice: event.target.value }));
  };

  const handleSystemPromptChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setSettings(prev => ({ ...prev, systemPrompt: event.target.value }));
  };

  const handleTemperatureChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(event.target.value);
    setSettings(prev => ({ ...prev, temperature: value }));
  };

  const handleRefresh = async () => {
    setIsFetching(true);
    setFetchError(null);
    try {
      const response = await fetch('https://ai-voice-calling-3.onrender.com/constants');
      if (!response.ok) {
        throw new Error('Failed to fetch settings');
      }
      const data = await response.json();
      
      const fetchedSettings: Settings = {
        voice: data.voice || initialSettings.voice,
        systemPrompt: data.system_prompt || data.systemPrompt || initialSettings.systemPrompt,
        temperature: data.temperature !== undefined ? data.temperature : initialSettings.temperature,
      };
      
      setSettings(fetchedSettings);
      setSaveMessage('Settings refreshed successfully');
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error: any) {
      setFetchError(error.message || 'Failed to refresh settings');
    } finally {
      setIsFetching(false);
    }
  };

  if (isFetching && !settings.voice) {
    return (
      <div className="fixed inset-0 flex h-screen w-screen bg-gray-950 text-gray-100 items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p>Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 flex h-screen w-screen bg-gray-950 text-gray-100">
      <main className="flex-1 p-8 overflow-y-auto h-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Settings <span className="ml-1">⚙️</span></h1>
          <div className="flex items-center space-x-4">
            <button
              onClick={handleRefresh}
              disabled={isFetching}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-lg text-gray-200 flex items-center"
              title="Refresh Settings"
            >
              <svg className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582M20 20v-5h-.581M5.635 19A9 9 0 1 1 19 5.635" />
              </svg>
              {isFetching ? 'Refreshing...' : 'Refresh'}
            </button>
            <button
              onClick={() => window.history.back()}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-gray-200 flex items-center"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Dashboard
            </button>
          </div>
        </div>

        {/* Error Message */}
        {fetchError && (
          <div className="bg-red-900 border border-red-700 rounded-lg p-4 mb-6 max-w-4xl">
            <p className="text-red-200">Error: {fetchError}</p>
          </div>
        )}

        {/* Settings Card */}
        <div className="bg-gray-900 rounded-xl shadow-sm p-6 max-w-4xl">
          <h2 className="text-xl font-bold mb-6">OpenAI Model Configuration</h2>
          
          <div className="space-y-6">
            {/* Voice Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Voice
              </label>
              <select
                value={settings.voice}
                onChange={handleVoiceChange}
                disabled={isFetching}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-700 disabled:opacity-50"
              >
                {VOICE_OPTIONS.map(option => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-400 mt-1">
                Select the voice model for AI phone calls
              </p>
            </div>

            {/* System Prompt */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                System Prompt
              </label>
              <textarea
                value={settings.systemPrompt}
                onChange={handleSystemPromptChange}
                rows={6}
                disabled={isFetching}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-700 resize-vertical disabled:opacity-50"
                placeholder="Enter the system prompt that will guide the AI's behavior during calls..."
              />
              <p className="text-xs text-gray-400 mt-1">
                This prompt defines how the AI should behave during phone calls
              </p>
            </div>

            {/* Temperature */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Temperature: {settings.temperature}
              </label>
              <div className="flex items-center space-x-4">
                <span className="text-xs text-gray-400">0</span>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.temperature}
                  onChange={handleTemperatureChange}
                  disabled={isFetching}
                  className="flex-1 h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer slider disabled:opacity-50"
                />
                <span className="text-xs text-gray-400">2</span>
              </div>
              <div className="flex items-center space-x-2 mt-2">
                <input
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  value={settings.temperature}
                  onChange={handleTemperatureChange}
                  disabled={isFetching}
                  className="w-20 px-2 py-1 bg-gray-800 border border-gray-700 rounded text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-blue-700 disabled:opacity-50"
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Controls randomness: 0 = focused and deterministic, 2 = creative and random
              </p>
            </div>

            {/* Save Button */}
            <div className="flex items-center justify-between pt-4 border-t border-gray-800">
              <div>
                {saveMessage && (
                  <span className={`text-sm ${saveMessage.includes('success') ? 'text-green-400' : 'text-red-400'}`}>
                    {saveMessage}
                  </span>
                )}
              </div>
              <button
                onClick={handleSaveSettings}
                disabled={isLoading || isFetching}
                className="px-6 py-2 bg-blue-700 hover:bg-blue-800 disabled:bg-blue-900 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors duration-200"
              >
                {isLoading ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>

        {/* Preview Section */}
        <div className="bg-gray-900 rounded-xl shadow-sm p-6 max-w-4xl mt-6">
          <h3 className="text-lg font-bold mb-4">Current Configuration Preview</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Voice:</span>
              <span className="text-gray-200">{settings.voice}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Temperature:</span>
              <span className="text-gray-200">{settings.temperature}</span>
            </div>
            <div>
              <span className="text-gray-400">System Prompt:</span>
              <div className="mt-1 p-3 bg-gray-800 rounded border-l-4 border-blue-700">
                <p className="text-gray-200 text-xs leading-relaxed">
                  {settings.systemPrompt || 'No system prompt set'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}