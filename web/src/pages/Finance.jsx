import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { MetricCard } from '../components/ui/Charts';
import { PaymentModal } from '../components/PaymentModal';
import { DollarSign, Plus, FileText, CheckCircle2, Clock } from 'lucide-react';

export function Finance() {
  const [summary, setSummary] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [rates, setRates] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);

  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  const loadFinanceData = async () => {
    try {
      setLoading(true);
      const [sum, invs, rts, cls] = await Promise.all([
        api.getFinanceSummary(),
        api.getInvoices(),
        api.getTuitionRates(),
        api.getClasses(),
      ]);
      setSummary(sum);
      setInvoices(invs || []);
      setRates(rts || []);
      setClasses(cls || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFinanceData();
  }, []);

  const handleGenerateClassInvoices = async (classId) => {
    try {
      await api.createInvoice({
        student_id: 1, // sample
        term: 'Term 1',
        amount: 100.0,
      });
      loadFinanceData();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRecordPayment = async (invoiceId, paymentData) => {
    await api.recordPayment(invoiceId, paymentData);
    loadFinanceData();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Finance & Fee Accounting</h2>
          <p className="text-xs text-slate-500">
            Tenant Private Accounting Block • Firewalled from State Ministry Oversight
          </p>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard
          title="Total Invoiced Tuition"
          value={`$${(summary?.total_invoices || 0).toLocaleString()}`}
          subtitle={`${summary?.invoice_count || 0} invoices issued`}
          icon={DollarSign}
        />
        <MetricCard
          title="Collected Revenue"
          value={`$${(summary?.collected_revenue || 0).toLocaleString()}`}
          subtitle={`${summary?.paid_invoices_count || 0} invoices fully settled`}
          trend="up"
          icon={CheckCircle2}
        />
        <MetricCard
          title="Outstanding Balance"
          value={`$${(summary?.pending_amount || 0).toLocaleString()}`}
          subtitle="Pending student payments"
          trend="down"
          icon={Clock}
        />
      </div>

      {/* Invoices List */}
      <Card title="Tuition Invoices & Payment Status" subtitle="Student billing ledgers">
        {loading ? (
          <div className="py-8 text-center text-xs text-slate-400">Loading accounting records...</div>
        ) : invoices.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No invoices issued yet for this academic term.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Invoice #</th>
                  <th className="px-4 py-3">Student</th>
                  <th className="px-4 py-3">Term</th>
                  <th className="px-4 py-3">Total Billed</th>
                  <th className="px-4 py-3">Paid Amount</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{inv.invoice_number}</td>
                    <td className="px-4 py-3">
                      <span className="font-semibold text-slate-800 block">{inv.student_name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{inv.roll_number}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{inv.term}</td>
                    <td className="px-4 py-3 font-bold text-slate-900">${inv.amount.toFixed(2)}</td>
                    <td className="px-4 py-3 text-emerald-700 font-semibold">${(inv.paid_amount || 0).toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={inv.status === 'paid' ? 'success' : inv.status === 'partially_paid' ? 'warning' : 'danger'}>
                        {inv.status?.replace('_', ' ')}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {inv.status !== 'paid' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setSelectedInvoice(inv);
                            setPaymentModalOpen(true);
                          }}
                        >
                          Record Payment
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <PaymentModal
        isOpen={paymentModalOpen}
        onClose={() => setPaymentModalOpen(false)}
        invoice={selectedInvoice}
        onRecordPayment={handleRecordPayment}
      />
    </div>
  );
}
