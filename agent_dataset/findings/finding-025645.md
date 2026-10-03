---
id: 25645
severity: "Medium"
---

# Incorrect initial deposit calculation may cause cancelProgram to revert

## Description



## Proof of Concept

## Impact

When governance parameters increase after program creation, `cancelProgram()` calculates higher buffer requirement than originally deposited, returning more funds to treasury than expected which may cause transaction revert due to insufficient fund balance. This cause inability to cancel the program.

When governance parameters decrease after program creation, `cancelProgram()` calculates lower buffer requirement than originally deposited, causing excess funds to remain in the contract while treasury receives less than the original deposit amount.

## Recommendation

Store the original `initialDeposit` amount in the program struct and use it during cancellation:

```solidity
struct EPProgram {
    // ... existing fields ...
    uint256 initialDeposit;
}

// In fundProgram():
programs[programId].initialDeposit = initialDeposit;

// In cancelProgram():
token.transfer(TREASURY, programs[programId].initialDeposit);
```

This ensures the exact deposited amount is returned regardless of governance parameter changes.
