---
id: 25333
severity: "Low/Info"
---

# LoanManager code optimizations: redundant impairment functions.

## Description

The LoanManager contract has the following code:

```solidity
function impairLoan(address loan_) {
    bool isGovernor_ = msg.sender == _governor();
    (...)
    if (isGovernor_) {
        _accountForLoanImpairmentAsGovernor(loan_);
    } else {
        _accountForLoanImpairment(loan_);
    }
}
function _accountForLoanImpairment(address loan_) {
    impairedDate_ = _accountForLoanImpairment(loan_, false);
}
function _accountForLoanImpairmentAsGovernor(address loan_) {
    impairedDate_ = _accountForLoanImpairment(loan_, true);
}
```

In this code, functions _accountForLoanImpairment(loan) and _accountForLoanImpairmentAsGovernor(loan) add unneeded redundancy and make the code more cluttered, therefore more difficult to read and less gas efficient.

## Proof of Concept

No PoC provided.

## Recommendation

Function impairLoan() can call directly accountForLoanImpairment(loan, isGovernor), and functions _accountForLoanImpairment(loan) and _accountForLoanImpairmentAsGovernor(loan) can be removed. Changing the same code to just:

```solidity
function impairLoan(address loan_){
    bool isGovernor_ = msg.sender == _governor();
    (...)
    _accountForLoanImpairment(loan_, isGovernor_);
}
```

Note: This suggestion would require a minor change to triggerDefault(), sending false as the second function parameter on the call to function _accountForLoanImpairment.
