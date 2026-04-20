import { useState, useEffect } from 'react'
import { userProfileService, UserPreferences, UserProfileData } from '../services/userProfileService'
import VisaIframeAuth from './VisaIframeAuth'

interface User {
  username: string
  email?: string
  userId: string
  name?: string
}

interface UserProfileProps {
  user: User
  isOpen: boolean
  onClose: () => void
}

const UserProfile = ({ user, isOpen, onClose }: UserProfileProps) => {
  const [profile, setProfile] = useState<UserProfileData | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editMode, setEditMode] = useState(false)
  const [showVisaAuth, setShowVisaAuth] = useState(false)
  const [showCardForm, setShowCardForm] = useState(false)
  const [pendingCardData, setPendingCardData] = useState<any>(null)
  const [cardOnboardingMode, setCardOnboardingMode] = useState<'primary' | 'backup' | null>(null)
  const [tempCardForm, setTempCardForm] = useState({
    cardNumber: '',
    cardholderName: '',
    cvv: '',
    expirationMonth: '',
    expirationYear: ''
  })
  const [formData, setFormData] = useState({
    name: user.name || user.username,
    email: user.email || '',
    address: '',
    notes: '',
    travelBudget: 'mid-range',
    travelInterests: [] as string[],
    accommodationType: 'hotels',
    travelStyle: 'balanced',
    shoppingCategories: [] as string[],
    priceRange: '50-200',
    sustainablePreference: false,
    notifications: true,
    emailUpdates: true,
    primaryCard: { type: '', cardNumber: '', cardholderName: '', expiryMonth: '', expiryYear: '', cvv: '' },
    backupCard: { type: '', cardNumber: '', cardholderName: '', expiryMonth: '', expiryYear: '', cvv: '' },
    useBackupCard: false
  })

  const travelInterestOptions = [
    'Adventure', 'Culture', 'Food & Dining', 'Nature', 'History', 
    'Art & Museums', 'Nightlife', 'Shopping', 'Beach', 'Mountains'
  ]

  const shoppingCategoryOptions = [
    'Electronics', 'Outdoor Gear', 'Fashion', 'Home & Garden', 
    'Books', 'Health & Beauty', 'Sports', 'Photography', 'Travel Gear'
  ]

  // Load user profile when modal opens
  useEffect(() => {
    if (isOpen) {
      loadProfile()
    }
  }, [isOpen, user.userId])

  const loadProfile = async () => {
    try {
      setLoading(true)
      setError(null)
      const userProfile = await userProfileService.getUserProfile(user.userId)
      setProfile(userProfile)
      
      if (userProfile && userProfile.preferences) {
        // Get payment info and convert from onboard_card format if needed
        const paymentInfo = (userProfile.preferences as any).payment || {}
        
        // Convert primary card format and preserve VIC session IDs
        const primaryCard = paymentInfo.primaryCard || {}
        const convertedPrimaryCard = {
          type: primaryCard.type || '',
          cardNumber: primaryCard.cardNumber || '',
          cardholderName: primaryCard.cardholderName || '',
          expiryMonth: primaryCard.expirationDate ? primaryCard.expirationDate.split('/')[0] : (primaryCard.expiryMonth || ''),
          expiryYear: primaryCard.expirationDate ? primaryCard.expirationDate.split('/')[1] : (primaryCard.expiryYear || ''),
          cvv: primaryCard.cvv ? '***' : '',
          vProvisionedTokenId: primaryCard.vProvisionedTokenId || '',
          // Preserve VIC session IDs for purchase flow
          consumerId: primaryCard.consumerId,
          clientDeviceId: primaryCard.clientDeviceId,
          clientReferenceId: primaryCard.clientReferenceId
        }
        
        // Convert backup card format and preserve VIC session IDs
        const backupCard = paymentInfo.backupCard || {}
        const convertedBackupCard = {
          type: backupCard.type || '',
          cardNumber: backupCard.cardNumber || '',
          cardholderName: backupCard.cardholderName || '',
          expiryMonth: backupCard.expirationDate ? backupCard.expirationDate.split('/')[0] : (backupCard.expiryMonth || ''),
          expiryYear: backupCard.expirationDate ? backupCard.expirationDate.split('/')[1] : (backupCard.expiryYear || ''),
          cvv: backupCard.cvv ? '***' : '',
          vProvisionedTokenId: backupCard.vProvisionedTokenId || '',
          // Preserve VIC session IDs for purchase flow
          consumerId: backupCard.consumerId,
          clientDeviceId: backupCard.clientDeviceId,
          clientReferenceId: backupCard.clientReferenceId
        }
        
        // Populate form data from profile
        setFormData({
          name: userProfile.name || user.username,
          email: userProfile.email || user.email || '',
          address: userProfile.address || '',
          notes: (userProfile as any).notes || '',
          travelBudget: userProfile.preferences.travel?.budget_range || 'mid-range',
          travelInterests: userProfile.preferences.travel?.interests || [],
          accommodationType: userProfile.preferences.travel?.accommodation_type || 'hotels',
          travelStyle: userProfile.preferences.travel?.travel_style || 'balanced',
          shoppingCategories: userProfile.preferences.shopping?.categories || [],
          priceRange: userProfile.preferences.shopping?.price_range || '50-200',
          sustainablePreference: userProfile.preferences.shopping?.sustainable_preference || false,
          notifications: userProfile.preferences.communication?.notifications || true,
          emailUpdates: userProfile.preferences.communication?.email_updates || true,
          primaryCard: convertedPrimaryCard,
          backupCard: convertedBackupCard,
          useBackupCard: !!backupCard.type
        })
      }
    } catch (err) {
      console.error('Error loading profile:', err)
      setError('Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

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

  const handleSave = async () => {
    setSaving(true)
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
        payment: {
          primaryCard: formData.primaryCard,  // Now includes VIC session IDs
          backupCard: formData.backupCard,    // Now includes VIC session IDs
          useBackupCard: formData.useBackupCard
        }
      } as any

      if (profile) {
        // Update existing profile
        await userProfileService.updateUserProfile(user.userId, {
          name: formData.name,
          email: formData.email,
          address: formData.address,
          notes: formData.notes,
          preferences
        } as any)
      } else {
        // Create new profile
        await userProfileService.createUserProfile(
          formData.email,
          formData.name,
          preferences,
          user.userId
        )
      }

      console.log('✅ Profile saved successfully')
      setEditMode(false)
      await loadProfile() // Reload to get updated data
    } catch (error) {
      console.error('❌ Error saving profile:', error)
      setError('Failed to save profile')
    } finally {
      setSaving(false)
    }
  }

  const handleCancel = () => {
    setEditMode(false)
    // Reset form data to current profile
    if (profile && profile.preferences) {
      const paymentInfo = (profile.preferences as any).payment || {}
      
      const primaryCard = paymentInfo.primaryCard || {}
      const convertedPrimaryCard = {
        type: primaryCard.type || '',
        cardNumber: primaryCard.cardNumber || '',
        cardholderName: primaryCard.cardholderName || '',
        expiryMonth: primaryCard.expirationDate ? primaryCard.expirationDate.split('/')[0] : (primaryCard.expiryMonth || ''),
        expiryYear: primaryCard.expirationDate ? '20' + primaryCard.expirationDate.split('/')[1] : (primaryCard.expiryYear || ''),
        cvv: primaryCard.cvv ? '***' : '',
        vProvisionedTokenId: primaryCard.vProvisionedTokenId || '',
        // Preserve VIC session IDs for purchase flow
        consumerId: primaryCard.consumerId,
        clientDeviceId: primaryCard.clientDeviceId,
        clientReferenceId: primaryCard.clientReferenceId
      }

      const backupCard = paymentInfo.backupCard || {}
      const convertedBackupCard = {
        type: backupCard.type || '',
        cardNumber: backupCard.cardNumber || '',
        cardholderName: backupCard.cardholderName || '',
        expiryMonth: backupCard.expirationDate ? backupCard.expirationDate.split('/')[0] : (backupCard.expiryMonth || ''),
        expiryYear: backupCard.expirationDate ? '20' + backupCard.expirationDate.split('/')[1] : (backupCard.expiryYear || ''),
        cvv: backupCard.cvv ? '***' : '',
        vProvisionedTokenId: backupCard.vProvisionedTokenId || '',
        // Preserve VIC session IDs for purchase flow
        consumerId: backupCard.consumerId,
        clientDeviceId: backupCard.clientDeviceId,
        clientReferenceId: backupCard.clientReferenceId
      }
      
      setFormData({
        name: profile.name || user.username,
        email: profile.email || user.email || '',
        address: profile.address || '',
        notes: (profile as any).notes || '',
        travelBudget: profile.preferences.travel?.budget_range || 'mid-range',
        travelInterests: profile.preferences.travel?.interests || [],
        accommodationType: profile.preferences.travel?.accommodation_type || 'hotels',
        travelStyle: profile.preferences.travel?.travel_style || 'balanced',
        shoppingCategories: profile.preferences.shopping?.categories || [],
        priceRange: profile.preferences.shopping?.price_range || '50-200',
        sustainablePreference: profile.preferences.shopping?.sustainable_preference || false,
        notifications: profile.preferences.communication?.notifications || true,
        emailUpdates: profile.preferences.communication?.email_updates || true,
        primaryCard: convertedPrimaryCard,
        backupCard: convertedBackupCard,
        useBackupCard: !!backupCard.type
      })
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl max-w-xl w-[90%] max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        <div className="flex justify-between items-center p-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">User Profile</h2>
          <div className="flex gap-2">
            <button 
              onClick={loadProfile}
              title="Refresh profile"
              className="p-2 text-blue-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 10C21 10 18.995 7.26822 17.3662 5.63824C15.7373 4.00827 13.4864 3 11 3C6.02944 3 2 7.02944 2 12C2 16.9706 6.02944 21 11 21C15.1031 21 18.5649 18.2543 19.6482 14.5M21 10V4M21 10H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors" onClick={onClose}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M18 6L6 18M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
              <div className="loading-spinner"></div>
              <span>Loading profile...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-gray-500">
              <span className="text-3xl">⚠️</span>
              <span>{error}</span>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors" onClick={loadProfile}>
                Retry
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {/* Basic Information */}
              <div className="pb-6 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Basic Information</h3>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="profile-name" className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                    <input
                      id="profile-name"
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="profile-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input
                      id="profile-email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="profile-address" className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                    <input
                      id="profile-address"
                      type="text"
                      value={formData.address}
                      onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
                    />
                  </div>
                  <div>
                    <label htmlFor="profile-notes" className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                    <textarea
                      id="profile-notes"
                      value={formData.notes}
                      onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                      disabled={!editMode}
                      rows={4}
                      placeholder="Add any additional notes or preferences..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500 resize-y"
                    />
                  </div>
                </div>
              </div>

              {/* Travel Preferences */}
              <div className="pb-6 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Travel Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Budget Range</label>
                    <select
                      value={formData.travelBudget}
                      onChange={(e) => setFormData(prev => ({ ...prev, travelBudget: e.target.value }))}
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
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
                            disabled={!editMode}
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
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
                    >
                      <option value="hotels">Hotels</option>
                      <option value="hostels">Hostels</option>
                      <option value="vacation-rentals">Vacation Rentals</option>
                      <option value="mixed">Mixed</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Shopping Preferences */}
              <div className="pb-6 border-b border-gray-200">
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
                            disabled={!editMode}
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
                      disabled={!editMode}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-blue-600 disabled:bg-gray-50 disabled:text-gray-500"
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
                        disabled={!editMode}
                        className="rounded"
                      />
                      Prefer sustainable/eco-friendly products
                    </label>
                  </div>
                </div>
              </div>

              {/* Communication Preferences */}
              <div className="pb-6 border-b border-gray-200">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Communication Preferences</h3>
                <div className="space-y-3">
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.notifications}
                      onChange={(e) => setFormData(prev => ({ ...prev, notifications: e.target.checked }))}
                      disabled={!editMode}
                      className="rounded"
                    />
                    Enable notifications
                  </label>

                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.emailUpdates}
                      onChange={(e) => setFormData(prev => ({ ...prev, emailUpdates: e.target.checked }))}
                      disabled={!editMode}
                      className="rounded"
                    />
                    Receive email updates
                  </label>
                </div>
              </div>

              {/* Payment Cards */}
              <div className="pb-6">
                <h3 className="text-base font-semibold text-gray-800 mb-4">Payment Cards</h3>

                {/* Card input form overlay */}
                {showCardForm && (
                  <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0,0,0,0.7)',
                    zIndex: 2000,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <div style={{
                      backgroundColor: 'white',
                      borderRadius: '12px',
                      padding: '2rem',
                      maxWidth: '450px',
                      width: '90%'
                    }}>
                      <h3 style={{ marginBottom: '1.5rem' }}>💳 Enter Card Details</h3>

                      <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                          Card Number
                        </label>
                        <input
                          type="text"
                          value={tempCardForm.cardNumber}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\s/g, '').replace(/(\d{4})/g, '$1 ').trim()
                            if (value.replace(/\s/g, '').length <= 19) {
                              setTempCardForm(prev => ({ ...prev, cardNumber: value }))
                            }
                          }}
                          placeholder="1234 5678 9012 3456"
                          maxLength={19}
                          style={{
                            width: '100%',
                            padding: '0.75rem',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                            fontSize: '1rem'
                          }}
                        />
                      </div>

                      <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                          Name on Card
                        </label>
                        <input
                          type="text"
                          value={tempCardForm.cardholderName}
                          onChange={(e) => setTempCardForm(prev => ({ ...prev, cardholderName: e.target.value }))}
                          placeholder="JOHN DOE"
                          style={{
                            width: '100%',
                            padding: '0.75rem',
                            border: '1px solid #ddd',
                            borderRadius: '4px',
                            fontSize: '1rem'
                          }}
                        />
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                            Month
                          </label>
                          <select
                            value={tempCardForm.expirationMonth}
                            onChange={(e) => setTempCardForm(prev => ({ ...prev, expirationMonth: e.target.value }))}
                            style={{
                              width: '100%',
                              padding: '0.75rem',
                              border: '1px solid #ddd',
                              borderRadius: '4px',
                              fontSize: '1rem'
                            }}
                          >
                            <option value="">MM</option>
                            {Array.from({ length: 12 }, (_, i) => i + 1).map(month => (
                              <option key={month} value={month.toString().padStart(2, '0')}>
                                {month.toString().padStart(2, '0')}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                            Year
                          </label>
                          <select
                            value={tempCardForm.expirationYear}
                            onChange={(e) => setTempCardForm(prev => ({ ...prev, expirationYear: e.target.value }))}
                            style={{
                              width: '100%',
                              padding: '0.75rem',
                              border: '1px solid #ddd',
                              borderRadius: '4px',
                              fontSize: '1rem'
                            }}
                          >
                            <option value="">YYYY</option>
                            {Array.from({ length: 15 }, (_, i) => new Date().getFullYear() + i).map(year => (
                              <option key={year} value={year}>
                                {year}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
                            CVV
                          </label>
                          <input
                            type="text"
                            value={tempCardForm.cvv}
                            onChange={(e) => {
                              if (/^\d{0,4}$/.test(e.target.value)) {
                                setTempCardForm(prev => ({ ...prev, cvv: e.target.value }))
                              }
                            }}
                            placeholder="123"
                            maxLength={4}
                            style={{
                              width: '100%',
                              padding: '0.75rem',
                              border: '1px solid #ddd',
                              borderRadius: '4px',
                              fontSize: '1rem'
                            }}
                          />
                        </div>
                      </div>

                      <div style={{
                        padding: '1rem',
                        backgroundColor: '#f0f9ff',
                        borderRadius: '8px',
                        marginBottom: '1.5rem'
                      }}>
                        <div style={{ fontSize: '0.875rem', color: '#0369a1' }}>
                          <strong>🔒 Secure Authentication</strong>
                          <p style={{ margin: '0.5rem 0 0 0' }}>
                            After entering your card details, you'll authenticate using Face ID, Touch ID, or Windows Hello.
                          </p>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '1rem' }}>
                        <button
                          onClick={() => {
                            setShowCardForm(false)
                            setTempCardForm({ cardNumber: '', cardholderName: '', cvv: '', expirationMonth: '', expirationYear: '' })
                          }}
                          style={{
                            flex: 1,
                            padding: '0.75rem',
                            border: '1px solid #ddd',
                            borderRadius: '8px',
                            backgroundColor: 'white',
                            cursor: 'pointer',
                            fontWeight: '500'
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => {
                            // Validate and proceed to iframe auth
                            const cardNumberClean = tempCardForm.cardNumber.replace(/\s/g, '')
                            if (cardNumberClean.length >= 13 && tempCardForm.cardholderName.trim() &&
                                tempCardForm.cvv.length >= 3 && tempCardForm.expirationMonth && tempCardForm.expirationYear) {
                              setPendingCardData({
                                cardNumber: cardNumberClean,
                                cardholderName: tempCardForm.cardholderName,
                                cvv: tempCardForm.cvv,
                                expirationMonth: tempCardForm.expirationMonth,
                                expirationYear: tempCardForm.expirationYear
                              })
                              setShowCardForm(false)
                              setShowVisaAuth(true)
                            } else {
                              setError('Please fill in all card details')
                            }
                          }}
                          disabled={!tempCardForm.cardNumber || !tempCardForm.cardholderName || !tempCardForm.cvv || !tempCardForm.expirationMonth || !tempCardForm.expirationYear}
                          style={{
                            flex: 1,
                            padding: '0.75rem',
                            border: 'none',
                            borderRadius: '8px',
                            backgroundColor: tempCardForm.cardNumber && tempCardForm.cardholderName && tempCardForm.cvv && tempCardForm.expirationMonth && tempCardForm.expirationYear
                              ? '#1a1f71' : '#ccc',
                            color: 'white',
                            cursor: tempCardForm.cardNumber && tempCardForm.cardholderName && tempCardForm.cvv && tempCardForm.expirationMonth && tempCardForm.expirationYear
                              ? 'pointer' : 'not-allowed',
                            fontWeight: '500'
                          }}
                        >
                          Continue to Authentication
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Visa iframe authentication overlay */}
                {showVisaAuth && pendingCardData && (
                  <div className="fixed inset-0 bg-black/70 z-[2000] flex items-center justify-center p-5">
                    <div className="bg-white rounded-xl max-w-[420px] w-full max-h-[80vh] overflow-hidden shadow-xl">
                      <VisaIframeAuth
                        userEmail={user.email || formData.email}
                        cardData={pendingCardData}
                        onComplete={async (result) => {
                          console.log('✅ Visa card onboarded:', result)
                          
                          // Save card to AppSync with VIC session IDs for purchase flow
                          try {
                            await userProfileService.addPaymentCard(user.userId, {
                              vProvisionedTokenId: result.vProvisionedTokenId,
                              lastFour: result.lastFour,
                              type: result.type,
                              expirationDate: result.expirationDate,
                              cardholderName: pendingCardData.cardholderName,
                              isPrimary: cardOnboardingMode === 'primary', // Set based on which card slot
                              // VIC session IDs needed for purchase flow
                              consumerId: result.consumerId,
                              clientDeviceId: result.clientDeviceId,
                              clientReferenceId: result.clientReferenceId
                            })
                            console.log('✅ Card saved to AppSync with VIC session IDs')
                            console.log('  consumerId:', result.consumerId)
                            console.log('  clientDeviceId:', result.clientDeviceId)
                            console.log('  clientReferenceId:', result.clientReferenceId)
                          } catch (err) {
                            console.error('⚠️ Failed to save card to AppSync:', err)
                          }

                          // Update form data with tokenized card info including VIC session IDs
                          const cardInfo = {
                            type: 'Visa',
                            cardNumber: result.lastFour,
                            cardholderName: pendingCardData.cardholderName,
                            expiryMonth: result.expirationDate.split('/')[0],
                            expiryYear: result.expirationDate.split('/')[1],
                            cvv: '***',
                            vProvisionedTokenId: result.vProvisionedTokenId,
                            // CRITICAL: Include VIC session IDs in form state to prevent overwriting on save
                            consumerId: result.consumerId,
                            clientDeviceId: result.clientDeviceId,
                            clientReferenceId: result.clientReferenceId
                          }

                          if (cardOnboardingMode === 'primary') {
                            setFormData(prev => ({ ...prev, primaryCard: cardInfo }))
                          } else if (cardOnboardingMode === 'backup') {
                            setFormData(prev => ({ ...prev, backupCard: cardInfo, useBackupCard: true }))
                          }

                          setShowVisaAuth(false)
                          setPendingCardData(null)
                          setCardOnboardingMode(null)
                        }}
                        onError={(errorMsg) => {
                          console.error('❌ Visa card onboarding error:', errorMsg)
                          setError(errorMsg)
                          setShowVisaAuth(false)
                          setPendingCardData(null)
                          setCardOnboardingMode(null)
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Primary Card */}
                <div className="card-subsection">
                  <h4>Primary Card</h4>
                  {formData.primaryCard.type && !editMode ? (
                    // Display mode - show stored card
                    <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                      <div><strong>Type:</strong> {formData.primaryCard.type}</div>
                      <div><strong>Card:</strong> **** **** **** {formData.primaryCard.cardNumber}</div>
                      <div><strong>Expires:</strong> {formData.primaryCard.expiryMonth}/{formData.primaryCard.expiryYear}</div>
                      {formData.primaryCard.cardholderName && (
                        <div><strong>Name:</strong> {formData.primaryCard.cardholderName}</div>
                      )}
                    </div>
                  ) : editMode ? (
                    // Edit mode - show "Add Visa Card" button
                    <div>
                      {!formData.primaryCard.type ? (
                        <button
                          type="button"
                          onClick={() => {
                            setCardOnboardingMode('primary')
                            setShowCardForm(true)
                          }}
                          style={{
                            background: 'linear-gradient(135deg, #1668e3 0%, #1a1f71 100%)',
                            color: 'white',
                            border: 'none',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontWeight: '500',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                        >
                          <span>💳</span>
                          <span>Add Visa Card with Secure Authentication</span>
                          <span>🔐</span>
                        </button>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                          <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                            <div><strong>Type:</strong> {formData.primaryCard.type}</div>
                            <div><strong>Card:</strong> **** **** **** {formData.primaryCard.cardNumber}</div>
                            <div><strong>Expires:</strong> {formData.primaryCard.expiryMonth}/{formData.primaryCard.expiryYear}</div>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setFormData(prev => ({
                                ...prev,
                                primaryCard: { type: '', cardNumber: '', cardholderName: '', expiryMonth: '', expiryYear: '', cvv: '' }
                              }))
                            }}
                            style={{
                              background: '#fed7d7',
                              color: '#e53e3e',
                              border: 'none',
                              padding: '0.5rem 1rem',
                              borderRadius: '8px',
                              cursor: 'pointer'
                            }}
                          >
                            Remove Card
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ padding: '1rem', backgroundColor: '#fff3cd', borderRadius: '8px', color: '#856404' }}>
                      No primary card added. Click "Edit Profile" to add a card.
                    </div>
                  )}
                </div>

                {/* Backup Card */}
                {formData.useBackupCard ? (
                  <div className="card-subsection">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h4>Backup Card</h4>
                      {editMode && (
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, useBackupCard: false }))}
                          style={{
                            background: '#fed7d7',
                            color: '#e53e3e',
                            border: 'none',
                            padding: '0.5rem 1rem',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            fontSize: '0.875rem'
                          }}
                        >
                          Remove Backup Card
                        </button>
                      )}
                    </div>
                    {formData.backupCard.type ? (
                      <div style={{ padding: '1rem', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                        <div><strong>Type:</strong> {formData.backupCard.type}</div>
                        <div><strong>Card:</strong> **** **** **** {formData.backupCard.cardNumber}</div>
                        <div><strong>Expires:</strong> {formData.backupCard.expiryMonth}/{formData.backupCard.expiryYear}</div>
                      </div>
                    ) : null}
                  </div>
                ) : editMode && formData.primaryCard.type && (
                  <button
                    type="button"
                    onClick={() => {
                      setCardOnboardingMode('backup')
                      setShowCardForm(true)
                    }}
                    className="mt-4 px-6 py-3 bg-gradient-to-r from-[#1668e3] to-[#1a1f71] text-white rounded-lg font-medium hover:shadow-lg transition-all"
                  >
                    + Add Backup Card
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-gray-200">
          {!editMode ? (
            <>
              <button className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors" onClick={onClose}>
                Close
              </button>
              <button className="px-4 py-2 bg-[#1a1f71] text-white rounded-lg text-sm font-medium" onClick={() => setEditMode(true)}>
                Edit Profile
              </button>
            </>
          ) : (
            <>
              <button 
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm font-medium disabled:opacity-50" 
                onClick={handleCancel}
                disabled={saving}
              >
                Cancel
              </button>
              <button 
                className="px-4 py-2 bg-[#1a1f71] text-white rounded-lg text-sm font-medium disabled:opacity-50" 
                onClick={handleSave}
                disabled={saving || !formData.name.trim()}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default UserProfile
