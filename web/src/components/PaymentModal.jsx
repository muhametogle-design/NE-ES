import React, { useState } from 'react';
import { Button } from './ui/Button';
import { Input, Select } from './ui/Input';
import { X } from 'lucide-react';

export function PaymentModal({ isOpen, onClose, invoice, onRecordPayment }) {
  const [amount, setAmount] = useState(invoice ? String(invoice.amount - (invoice.paid_amount || 0)) : '');
  const [method, setMethod] = useState('Zaad');
  const [ref, setRef] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen || !invoice) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payAmount = parseFloat(amount);
    if (!payAmount || payAmount <= 0) {
      setError('Please enter a valid payment amount');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      await onRecordPayment(invoice.id, {
        amount: payAmount,
        payment_method: method,
        transaction_reference: ref || null,
      });
      onClose();
    } catch (err) {
      setError(err.message || 'Payment recording failed');
    } finally {
      setLoading(false);
    }
  };

  const outstanding = Math.max(0, invoice.amount - (invoice.paid_amount || 0));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full overflow-hidden border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-lg">Record Tuition Payment</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 bg-slate-50 border-b border-slate-100 text-xs text-slate-600 space-y-1">
          <div className="flex justify-between">
            <span className="font-semibold text-slate-700">Invoice:</span>
            <span className="font-mono">{invoice.invoice_number}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-semibold text-slate-700">Student:</span>
            <span>{invoice.student_name} ({invoice.roll_number})</span>
          </div>
          <div className="flex justify-between">
            <span className="font-semibold text-slate-700">Total Billed:</span>
            <span>${invoice.amount.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-semibold text-slate-700">Remaining Due:</span>
            <span className="font-bold text-emerald-700">${outstanding.toFixed(2)}</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <div className="p-3 bg-rose-50 text-rose-700 text-xs rounded-lg">{error}</div>}

          <Input
            label="Payment Amount ($ USD)"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />

          <Select
            label="Payment Method"
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            <option value="Zaad">Telesom Zaad Service</option>
            <option value="Sahal">Golis Sahal Service</option>
            <option value="EvcPlus">Hormuud EVC Plus</option>
            <option value="Bank Transfer">Dahabshiil / Premier Bank</option>
            <option value="Cash">Cash / Accounts Office</option>
          </Select>

          <Input
            label="Transaction Reference / Receipt #"
            placeholder="e.g. TXN-99882314"
            value={ref}
            onChange={(e) => setRef(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="outline" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" loading={loading}>
              Confirm Payment
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
