import { useState } from 'react'
import { userProfileService, UserPreferences } from '../services/userProfileService'

interface UserOnboardingProps {
  user: {
    username: string
    email?: string
    userId: string
    name?: string
  }
  onComplete: () => void
}

const UserOnboarding = ({ user, onComplete }: UserOnboardingProps) => {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: user.name || user.username || '',
    address: '',
    travelBudget: 'mid-range',
    travelInterests: [] as string[],
    accommodationType: 'hotels',
    travelStyle: 'balanced',
    shoppingCategories: [] as string[],
    priceRange: '50-200',
    sustainablePreference: false,
    notifications: true,
    emailUpdates: true
  })

  const travelInterestOptions = [
    'Adventure', 'Culture', 'Food & Dining', 'Nature', 'History', 
    'Art & Museums', 'Nightlife', 'Shopping', 'Beach', 'Mountains'
  ]

  const shoppingCategoryOptions = [
    'Electronics', 'Outdoor Gear', 'Fashion', 'Home & Garden', 
    'Books', 'Health & Beauty', 'Sports', 'Photography', 'Travel Gear'
  ]

  const handleInterestToggle = (interest: string) => {
    setFormData(prev => ({
      ...prev,
      travelInterests: prev.travelInterests.includes(interest)
        ? prev.travelInterests.filter(i => i !== interest)
        : [...prev.travelInterests, interest]
    }))
  }

  const handleCategoryToggle = (category: string) => {
    setFormData(prev => ({
      ...prev,
      shoppingCategories: prev.shoppingCategories.includes(category)
        ? prev.shoppingCategories.filter(c => c !== category)
        : [...prev.shoppingCategories, category]
    }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      const preferences: UserPreferences = {
        travel: {
          budget_range: formData.travelBudget,
          interests: formData.travelInterests,
          accommodation_type: formData.accommodationType,
          travel_style: formData.travelStyle
        },
        shopping: {
          categories: formData.shoppingCategories,
          price_range: formData.priceRange,
          sustainable_preference: formData.sustainablePreference
        },
        communication: {
          notifications: formData.notifications,
          email_updates: formData.emailUpdates,
          language: 'en'
        }
      }

      await userProfileService.createUserProfile(
        user.email || `${user.username}@example.com`,
        formData.name,
        preferences,
        user.userId,
        formData.address
      )

      console.log('✅ Onboarding completed successfully')
      onComplete()
    } catch (error) {
      console.error('❌ Error completing onboarding:', error)
      alert('There was an error setting up your profile. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl max-w-xl w-[90%] max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 text-center">
          <h2 className="text-xl font-semibold text-gray-800 mb-1">Welcome to AI Assistant!</h2>
          <p className="text-sm text-gray-500 mb-3">Let's set up your profile to provide personalized recommendations</p>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden mb-2">
            <div 
              className="h-full bg-gradient-to-r from-blue-500 to-blue-700 rounded-full transition-all duration-300"
              style={{ width: `${(step / 4) * 100}%` }}
            ></div>
          </div>
          <span className="text-xs text-gray-400 font-medium">Step {step} of 4</span>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="flex flex-col gap-6">
            {step === 1 && (
              <div className="pb-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Basic Information</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                    <input
                      id="name"
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="How should we address you?"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600"
                    />
                  </div>
                  <div>
                    <label htmlFor="address" className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                    <input
                      id="address"
                      type="text"
                      value={formData.address}
                      onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                      placeholder="Your address"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600"
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="pb-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Travel Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Budget Range</label>
                    <select
                      value={formData.travelBudget}
                      onChange={(e) => setFormData(prev => ({ ...prev, travelBudget: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600"
                    >
                      <option value="budget">Budget-friendly</option>
                      <option value="mid-range">Mid-range</option>
                      <option value="luxury">Luxury</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Travel Interests</label>
                    <div className="grid grid-cols-2 gap-2">
                      {travelInterestOptions.map(interest => (
                        <label key={interest} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.travelInterests.includes(interest)}
                            onChange={() => handleInterestToggle(interest)}
                            className="rounded"
                          />
                          {interest}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Accommodation Preference</label>
                    <select
                      value={formData.accommodationType}
                      onChange={(e) => setFormData(prev => ({ ...prev, accommodationType: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600"
                    >
                      <option value="hotels">Hotels</option>
                      <option value="hostels">Hostels</option>
                      <option value="vacation-rentals">Vacation Rentals</option>
                      <option value="mixed">Mixed</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="pb-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Shopping Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Categories</label>
                    <div className="grid grid-cols-2 gap-2">
                      {shoppingCategoryOptions.map(category => (
                        <label key={category} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={formData.shoppingCategories.includes(category)}
                            onChange={() => handleCategoryToggle(category)}
                            className="rounded"
                          />
                          {category}
                        </label>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Price Range</label>
                    <select
                      value={formData.priceRange}
                      onChange={(e) => setFormData(prev => ({ ...prev, priceRange: e.target.value }))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600"
                    >
                      <option value="0-50">$0 - $50</option>
                      <option value="50-200">$50 - $200</option>
                      <option value="200-500">$200 - $500</option>
                      <option value="500+">$500+</option>
                    </select>
                  </div>

                  <div>
                    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.sustainablePreference}
                        onChange={(e) => setFormData(prev => ({ ...prev, sustainablePreference: e.target.checked }))}
                        className="rounded"
                      />
                      Prefer sustainable/eco-friendly products
                    </label>
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="pb-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Communication Preferences</h3>
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.notifications}
                      onChange={(e) => setFormData(prev => ({ ...prev, notifications: e.target.checked }))}
                      className="rounded"
                    />
                    Enable notifications
                  </label>

                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.emailUpdates}
                      onChange={(e) => setFormData(prev => ({ ...prev, emailUpdates: e.target.checked }))}
                      className="rounded"
                    />
                    Receive email updates
                  </label>
                </div>

                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h4 className="text-sm font-semibold text-gray-800 mb-3">Summary</h4>
                  <div className="space-y-1 text-sm text-gray-600">
                    <p><span className="font-medium text-gray-700">Name:</span> {formData.name}</p>
                    <p><span className="font-medium text-gray-700">Travel Budget:</span> {formData.travelBudget}</p>
                    <p><span className="font-medium text-gray-700">Travel Interests:</span> {formData.travelInterests.join(', ') || 'None selected'}</p>
                    <p><span className="font-medium text-gray-700">Shopping Categories:</span> {formData.shoppingCategories.join(', ') || 'None selected'}</p>
                    <p><span className="font-medium text-gray-700">Price Range:</span> ${formData.priceRange}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 p-4 border-t border-gray-200">
          {step > 1 && (
            <button 
              onClick={() => setStep(step - 1)}
              disabled={loading}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Back
            </button>
          )}
          
          {step < 4 ? (
            <button 
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !formData.name.trim()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              Next
            </button>
          ) : (
            <button 
              onClick={handleSubmit}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading ? 'Setting up...' : 'Complete Setup'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default UserOnboarding
