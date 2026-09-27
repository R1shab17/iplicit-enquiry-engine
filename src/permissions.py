"""
RequiredPermissions lookup table for iplicit DbEnquiry exports.

Every enquiry needs at least one entry in RequiredPermissions
(AttributeOperationId) or the Create button stays disabled in the UI with
no visible error (see docs/FAILURE_MODES.md #4). These GUIDs are the
system-seeded attribute-operation ids observed across the 640-definition
corpus explored to build this repo (see docs/ARCHITECTURE.md).

Status: Confirmed, except where noted. `AP.Enquiry` does not have a
confirmed GUID distinct from `AR.Enquiry` yet — generated/ap/*.json
currently reuses AR.Enquiry's id as a working placeholder. See
docs/ROADMAP.md item 2.
"""

PERM = {
    "GeneralLedger.Enquiry": "693B164B-B59F-4946-97B7-CD01465847A7",
    "GeneralLedger.TrialBalance": "57257282-A05B-49EA-A625-1AEE2BF5F941",
    "GeneralLedger.ProfitLoss": "FC25F7A9-2A3C-471A-8A4E-6DD29434F3D9",
    "GeneralLedger.BalanceSheet": "F4EB155F-D660-46B2-A84E-47395EFD2A82",
    "GeneralLedger.FinancialStatements": "1245D473-C508-4301-95A2-AE6A46D547C3",
    "Customer.Enquiry": "DC6FF301-E2D6-4933-8CEF-3347F7DDD177",
    "Supplier.Enquiry": "9B4A71B5-8D55-420F-A876-4F8DF2C1E7BE",
    "SaleInvoice.Enquiry": "39E3B643-9552-457D-B402-82C2E9DB6B71",
    "PurchaseInvoice.Enquiry": "CF0EF798-1361-4D9D-8B8A-8CB7AFD2CA33",
    "PurchaseOrder.Enquiry": "DF4241B0-213E-47F9-971B-9CDDDA30FB90",
    "AR.Enquiry": "F15CFADC-7A9F-4443-8492-A8A1581B0D5F",
    "AR.CreditControl": "614BDC2F-13EC-455D-B0CE-504AE574ED03",
    "DocBase.Enquiry": "8891D6F9-6D92-4612-B367-D526C57F5A8D",
    "Account.Enquiry": "BC44A19C-6115-4449-8947-20BE34F68B1A",
    "BankReconciliation.Enquiry": "A879D371-33DA-4C5E-AF3B-E66FAFA28275",
    "Cashbook.Enquiry": "C212B965-02C9-4A27-A8C4-F9869D4ADC84",
    "Receipt.Enquiry": "DCC5113B-808E-4669-94F2-D2EC5D01AE56",
    "Payment.Enquiry": "EB62FCA0-71A2-4894-B652-400214654700",
    "VatReturn.Enquiry": "8E603BD5-2DAC-4359-9639-79B0DC3B020A",
    "ManualJournal.Enquiry": "20DF7F94-FC51-4A48-8D65-9D88F7075954",
    "BudgetForecast.Enquiry": "AF31AA72-1F3D-4352-9216-F4849A2B5166",
    "Project.FinancialStatements": "F20AAECE-BAF9-45B8-A87F-866EA8717E66",
    "UserAccount.Enquiry": "C421DF21-BE87-4533-86EE-7400480E9CB5",
    "TimesheetDoc.Enquiry": "015EFA02-F4D0-4FCA-83F0-1928BEEB948D",
}
