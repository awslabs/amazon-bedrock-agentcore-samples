import { useState } from 'react'
import CardOnboarding from './CardOnboarding'

const CardOnboardingTest = () => {
  const [showCard, setShowCard] = useState(false)
  const [result, setResult] = useState<any>(null)

  return (
    <div style={{ padding: '20px' }}>
      <h1>Visa Card Onboarding Test</h1>

      {!showCard && (
        <button
          onClick={() => setShowCard(true)}
          style={{
            padding: '10px 20px',
            fontSize: '16px',
            backgroundColor: '#007BFF',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Start Card Onboarding
        </button>
      )}

      {showCard && !result && (
        <CardOnboarding
          userEmail="test@example.com"
          onComplete={(cardInfo) => {
            console.log('Card onboarding complete:', cardInfo)
            setResult(cardInfo)
            setShowCard(false)
          }}
          onSkip={() => {
            console.log('Card onboarding skipped')
            setShowCard(false)
          }}
        />
      )}

      {result && (
        <div style={{ marginTop: '20px', padding: '20px', backgroundColor: '#d4edda', borderRadius: '4px' }}>
          <h2>✅ Success!</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
          <button
            onClick={() => { setResult(null); setShowCard(false) }}
            style={{
              marginTop: '10px',
              padding: '10px 20px',
              fontSize: '14px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Test Again
          </button>
        </div>
      )}

      <div style={{ marginTop: '40px', padding: '20px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
        <h3>Test Card Details:</h3>
        <ul>
          <li><strong>Card Number:</strong> 4622943123044159</li>
          <li><strong>CVV:</strong> 598</li>
          <li><strong>Expiry:</strong> 12/2026</li>
        </ul>
      </div>
    </div>
  )
}

export default CardOnboardingTest
