import { useState } from 'react'
import { showToast } from '../utils/toast'
import VisaIframeAuth from './VisaIframeAuth'

interface CardOnboardingProps {
  userEmail: string
  onComplete: (cardInfo: any) => void
  onSkip: () => void
}

const CardOnboarding = ({ userEmail, onComplete, onSkip }: CardOnboardingProps) => {
  const [step, setStep] = useState<'form' | 'iframe' | 'complete'>('form')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState({
    cardNumber: '',
    cardholderName: '',
    cvv: '',
    expMonth: '',
    expYear: '',
    isPrimary: true
  })

  const currentYear = new Date().getFullYear()
  const years = Array.from({ length: 10 }, (_, i) => currentYear + i)
  const months = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'))

  const formatCard = (v: string) => v.replace(/\s/g, '').replace(/(.{4})/g, '$1 ').trim()
  const isValid = form.cardNumber.replace(/\s/g, '').length >= 13 && 
                  form.cardholderName && form.cvv.length >= 3 && 
                  form.expMonth && form.expYear

  const handleSubmit = () => {
    setLoading(true)
    setError(null)
    setStep('iframe')
  }

  const inputClass = "w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
  const labelClass = "block text-sm font-medium text-gray-700 mb-1"

  if (step === 'complete') {
    return (
      <div className="text-center py-6">
        <div className="text-4xl mb-3">✅</div>
        <p className="font-medium text-gray-900">Card Added Successfully</p>
      </div>
    )
  }

  if (step === 'iframe') {
    return (
      <VisaIframeAuth
        userEmail={userEmail}
        cardData={{
          cardNumber: form.cardNumber,
          cardholderName: form.cardholderName,
          cvv: form.cvv,
          expirationMonth: form.expMonth,
          expirationYear: form.expYear
        }}
        onComplete={(result) => { setStep('complete'); setLoading(false); onComplete(result) }}
        onError={(msg) => {
          showToast.error(msg)
          setError(msg)
          setStep('form')
          setLoading(false)
        }}
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div style={{ marginBottom: '1rem' }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: '#1a202c', marginBottom: '0.25rem' }}>
          💳 Enter Card Details
        </h3>
        <p style={{ fontSize: '0.875rem', color: '#718096' }}>
          Your card will be securely verified with biometric authentication
        </p>
      </div>

      {error && <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md">⚠️ {error}</div>}

      <div>
        <label className={labelClass}>Card Number</label>
        <input
          type="text"
          value={form.cardNumber}
          onChange={(e) => setForm({ ...form, cardNumber: formatCard(e.target.value.slice(0, 19)) })}
          placeholder="1234 5678 9012 3456"
          className={inputClass}
        />
      </div>

      <div>
        <label className={labelClass}>Name on Card</label>
        <input
          type="text"
          value={form.cardholderName}
          onChange={(e) => setForm({ ...form, cardholderName: e.target.value })}
          placeholder="JOHN DOE"
          className={inputClass}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Expiration</label>
          <div className="flex gap-2">
            <select
              value={form.expMonth}
              onChange={(e) => setForm({ ...form, expMonth: e.target.value })}
              className={inputClass}
            >
              <option value="">MM</option>
              {months.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <select
              value={form.expYear}
              onChange={(e) => setForm({ ...form, expYear: e.target.value })}
              className={inputClass}
            >
              <option value="">YYYY</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>
        <div>
          <label className={labelClass}>CVV</label>
          <input
            type="text"
            value={form.cvv}
            onChange={(e) => /^\d{0,4}$/.test(e.target.value) && setForm({ ...form, cvv: e.target.value })}
            placeholder="123"
            className={inputClass}
          />
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={form.isPrimary}
          onChange={(e) => setForm({ ...form, isPrimary: e.target.checked })}
          className="rounded border-gray-300"
        />
        Set as primary payment method
      </label>

      {/* Secure Authentication Message */}
      <div style={{
        backgroundColor: '#f0f7ff',
        border: '1px solid #d0e7ff',
        borderRadius: '8px',
        padding: '0.75rem',
        display: 'flex',
        alignItems: 'start',
        gap: '0.5rem'
      }}>
        <span style={{ fontSize: '1.25rem' }}>🔐</span>
        <div style={{ fontSize: '0.875rem', color: '#1a1f71' }}>
          <strong>Secure Authentication</strong>
          <p style={{ marginTop: '0.25rem', color: '#4a5568' }}>
            After entering your card details, you'll authenticate using Face ID, Touch ID, or Windows Hello.
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', paddingTop: '0.75rem' }}>
        <button
          onClick={onSkip}
          disabled={loading}
          style={{
            flex: 1,
            padding: '0.75rem',
            border: '1px solid #ddd',
            borderRadius: '8px',
            backgroundColor: 'white',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight: '500',
            color: '#374151'
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading || !isValid}
          style={{
            flex: 1,
            padding: '0.75rem',
            border: 'none',
            borderRadius: '8px',
            backgroundColor: (loading || !isValid) ? '#ccc' : '#1a1f71',
            color: 'white',
            cursor: (loading || !isValid) ? 'not-allowed' : 'pointer',
            fontWeight: '500'
          }}
        >
          {loading ? 'Processing...' : 'Continue to Authentication'}
        </button>
      </div>
    </div>
  )
}

export default CardOnboarding
