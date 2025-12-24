import { useState } from 'react'

interface CardOnboardingFormProps {
  onSubmit: (cardData: { cardNumber: string; expirationDate: string; cvv: string; cardType: string }) => void
  onCancel: () => void
}

const CardOnboardingForm = ({ onSubmit, onCancel }: CardOnboardingFormProps) => {
  const [form, setForm] = useState({ cardNumber: '', expMonth: '', expYear: '', cvv: '', cardType: 'Visa' })

  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() + i)
  const months = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'))
  const formatCard = (v: string) => v.replace(/\s/g, '').replace(/(.{4})/g, '$1 ').trim()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      cardNumber: form.cardNumber.replace(/\s/g, ''),
      expirationDate: `${form.expMonth}/${form.expYear}`,
      cvv: form.cvv,
      cardType: form.cardType
    })
  }

  const inputClass = "w-full px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-900 bg-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
  const labelClass = "block text-sm font-medium text-gray-700 mb-1"

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Add Payment Card</h3>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className={labelClass}>Card Type</label>
            <select
              value={form.cardType}
              onChange={(e) => setForm({ ...form, cardType: e.target.value })}
              className={inputClass}
            >
              <option>Visa</option>
              <option>Mastercard</option>
              <option>American Express</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Card Number</label>
            <input
              type="text"
              value={form.cardNumber}
              onChange={(e) => setForm({ ...form, cardNumber: formatCard(e.target.value.slice(0, 19)) })}
              placeholder="1234 5678 9012 3456"
              className={inputClass}
              required
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className={labelClass}>Month</label>
              <select
                value={form.expMonth}
                onChange={(e) => setForm({ ...form, expMonth: e.target.value })}
                className={inputClass}
                required
              >
                <option value="">MM</option>
                {months.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Year</label>
              <select
                value={form.expYear}
                onChange={(e) => setForm({ ...form, expYear: e.target.value })}
                className={inputClass}
                required
              >
                <option value="">YY</option>
                {years.map(y => <option key={y} value={String(y).slice(-2)}>{String(y).slice(-2)}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>CVV</label>
              <input
                type="text"
                value={form.cvv}
                onChange={(e) => /^\d{0,4}$/.test(e.target.value) && setForm({ ...form, cvv: e.target.value })}
                placeholder="123"
                className={inputClass}
                required
              />
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md text-sm font-medium text-gray-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-[#1a1f71] hover:bg-[#2d3a8c] rounded-md text-sm font-medium text-white"
            >
              Add Card
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CardOnboardingForm
