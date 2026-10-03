---
id: 25684
severity: "Medium"
---

# Incorrect selector in FlashRolloverLoan_G5::_acceptCommitment() does not match SmartCommitmentForwarder::acceptCommitmentWithRecipient()

## Description



## Proof of Concept

## Vulnerability Detail

`FlashRolloverLoan_G5::_acceptCommitment()` accepts the commitment to `SmartCommitmentForwarder` if `_commitmentArgs.smartCommitmentAddress != address(0)`. However, the selector used is `acceptSmartCommitmentWithRecipient()`, which does not match `SmartCommitmentForwarder::acceptCommitmentWithRecipient()`, DoSing the ability to rollover loans for `LenderCommitmentGroup_Smart`.

## Impact

`FlashRolloverLoan_G5` will not work for `LenderCommitmentGroup_Smart` loans.

## Code Snippet

[FlashRolloverLoan_G5::_acceptCommitment()](<https://github.com/sherlock-audit/2024-04-teller-finance/blob/main/teller-protocol-v2-audit-2024/packages/contracts/contracts/LenderCommitmentForwarder/extensions/FlashRolloverLoan_G5.sol#L292>)

```solidity
function _acceptCommitment(
    address lenderCommitmentForwarder,
    address borrower,
    address principalToken,
    AcceptCommitmentArgs memory _commitmentArgs
)
    internal
    virtual
    returns (uint256 bidId_, uint256 acceptCommitmentAmount_)
{
    uint256 fundsBeforeAcceptCommitment = IERC20Upgradeable(principalToken)
        .balanceOf(address(this));

    if (_commitmentArgs.smartCommitmentAddress != address(0)) {

            bytes memory responseData = address(lenderCommitmentForwarder)
                .functionCall(
                    abi.encodePacked(
                        abi.encodeWithSelector(
                            ISmartCommitmentForwarder
                                .acceptSmartCommitmentWithRecipient
                                .selector,
                            _commitmentArgs.smartCommitmentAddress,
                            _commitmentArgs.principalAmount,
                            _commitmentArgs.collateralAmount,
                            _commitmentArgs.collateralTokenId,
                            _commitmentArgs.collateralTokenAddress,
                            address(this),
                            _commitmentArgs.interestRate,
                            _commitmentArgs.loanDuration
                        ),
                        borrower //cant be msg.sender because of the flash flow
                    )
                );

            (bidId_) = abi.decode(responseData, (uint256));
        ...
```

## Recommendation

Insert the correct selector, `SmartCommitmentForwarder::acceptCommitmentWithRecipient()`.
