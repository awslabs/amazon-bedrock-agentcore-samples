import { useState } from 'react'
import { userProfileService, UserPreferences } from '../services/userProfileService'
import CardOnboarding from './CardOnboarding'

interface UserOnboardingProps {
  user: {
    username: string
    email?: string
    userId: string
  }
  onComplete: () => void
}

const UserOnboarding = ({ user, onComplete }: UserOnboardingProps) => {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: user.username,
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
  const [cardInfo, setCardInfo] = useState<any>(null)

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

  const handleCardComplete = (cardData: any) => {
    console.log('✅ Card onboarding completed:', cardData)
    setCardInfo(cardData)
    // Auto-advance after successful card enrollment
    setTimeout(() => {
      handleSubmit()
    }, 2000)
  }

  const handleCardSkip = () => {
    console.log('⏭️ Skipped card onboarding')
    setCardInfo(null)
    handleSubmit()
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
        },
        // Include payment info if card was added
        ...(cardInfo && {
          payment: {
            primaryCard: {
              lastFour: cardInfo.lastFour,
              type: cardInfo.type,
              expirationDate: cardInfo.expirationDate,
              cardNumber: `**** **** **** ${cardInfo.lastFour}`,
              vProvisionedTokenId: cardInfo.vProvisionedTokenId
            }
          }
        })
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

  const totalSteps = 5 // Updated to include card onboarding step

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-modal">
        <div className="onboarding-header">
          <h2>Welcome to AI Assistant!</h2>
          <p>Let's set up your profile to provide personalized recommendations</p>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${(step / totalSteps) * 100}%` }}></div>
          </div>
          <span className="step-indicator">Step {step} of {totalSteps}</span>
        </div>

        <div className="onboarding-content">
          {step === 1 && (
            <div className="step-content">
              <h3>Basic Information</h3>
              <div className="form-group">
                <label htmlFor="name">Display Name</label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="How should we address you?"
                />
              </div>
              <div className="form-group">
                <label htmlFor="address">Address</label>
                <input
                  id="address"
                  type="text"
                  value={formData.address}
                  onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                  placeholder="Your address"
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="step-content">
              <h3>Travel Preferences</h3>

              <div className="form-group">
                <label>Budget Range</label>
                <select
                  value={formData.travelBudget}
                  onChange={(e) => setFormData(prev => ({ ...prev, travelBudget: e.target.value }))}
                >
                  <option value="budget">Budget-friendly</option>
                  <option value="mid-range">Mid-range</option>
                  <option value="luxury">Luxury</option>
                </select>
              </div>

              <div className="form-group">
                <label>Travel Interests (select all that apply)</label>
                <div className="checkbox-grid">
                  {travelInterestOptions.map(interest => (
                    <label key={interest} className="checkbox-item">
                      <input
                        type="checkbox"
                        checked={formData.travelInterests.includes(interest)}
                        onChange={() => handleInterestToggle(interest)}
                      />
                      {interest}
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label>Accommodation Preference</label>
                <select
                  value={formData.accommodationType}
                  onChange={(e) => setFormData(prev => ({ ...prev, accommodationType: e.target.value }))}
                >
                  <option value="hotels">Hotels</option>
                  <option value="hostels">Hostels</option>
                  <option value="vacation-rentals">Vacation Rentals</option>
                  <option value="mixed">Mixed</option>
                </select>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="step-content">
              <h3>Shopping Preferences</h3>

              <div className="form-group">
                <label>Preferred Categories (select all that apply)</label>
                <div className="checkbox-grid">
                  {shoppingCategoryOptions.map(category => (
                    <label key={category} className="checkbox-item">
                      <input
                        type="checkbox"
                        checked={formData.shoppingCategories.includes(category)}
                        onChange={() => handleCategoryToggle(category)}
                      />
                      {category}
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label>Price Range</label>
                <select
                  value={formData.priceRange}
                  onChange={(e) => setFormData(prev => ({ ...prev, priceRange: e.target.value }))}
                >
                  <option value="0-50">$0 - $50</option>
                  <option value="50-200">$50 - $200</option>
                  <option value="200-500">$200 - $500</option>
                  <option value="500+">$500+</option>
                </select>
              </div>

              <div className="form-group">
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={formData.sustainablePreference}
                    onChange={(e) => setFormData(prev => ({ ...prev, sustainablePreference: e.target.checked }))}
                  />
                  Prefer sustainable/eco-friendly products
                </label>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="step-content">
              <h3>Communication Preferences</h3>

              <div className="form-group">
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={formData.notifications}
                    onChange={(e) => setFormData(prev => ({ ...prev, notifications: e.target.checked }))}
                  />
                  Enable notifications
                </label>
              </div>

              <div className="form-group">
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={formData.emailUpdates}
                    onChange={(e) => setFormData(prev => ({ ...prev, emailUpdates: e.target.checked }))}
                  />
                  Receive email updates
                </label>
              </div>

              <div className="summary-section">
                <h4>Summary</h4>
                <p><strong>Name:</strong> {formData.name}</p>
                <p><strong>Travel Budget:</strong> {formData.travelBudget}</p>
                <p><strong>Travel Interests:</strong> {formData.travelInterests.join(', ') || 'None selected'}</p>
                <p><strong>Shopping Categories:</strong> {formData.shoppingCategories.join(', ') || 'None selected'}</p>
                <p><strong>Price Range:</strong> ${formData.priceRange}</p>
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="step-content">
              <CardOnboarding
                userEmail={user.email || `${user.username}@example.com`}
                onComplete={handleCardComplete}
                onSkip={handleCardSkip}
              />
            </div>
          )}
        </div>

        <div className="onboarding-actions">
          {step > 1 && step < 5 && (
            <button
              className="btn-secondary"
              onClick={() => setStep(step - 1)}
              disabled={loading}
            >
              Back
            </button>
          )}

          {step < 4 ? (
            <button
              className="btn-primary"
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !formData.name.trim()}
            >
              Next
            </button>
          ) : step === 4 ? (
            <button
              className="btn-primary"
              onClick={() => setStep(5)}
              disabled={loading}
            >
              Next
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default UserOnboarding
