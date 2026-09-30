---
id: 17878
severity: "High"
---

# Strategist can fail to withdraw asset token from a private vault

## Description

Calling the `AstariaRouter.withdraw` function calls the following `ERC4626RouterBase.withdraw` function; however, calling `ERC4626RouterBase.withdraw` function for a private vault reverts because the `Vault` contract does not have an `approve` function. Directly calling the `Vault.withdraw` function for a private vault can also revert since the `Vault` contract does not have a way to set the allowance for itself to transfer the asset token, which can cause many ERC20 tokens’ `transferFrom` function calls to revert when deducting the transfer amount from the allowance. Hence, after depositing some of the asset token in a private vault, the strategist can fail to withdraw this asset token from this private vault and lose this deposit.

```solidity
function withdraw(
    IERC4626 vault,
    address to,
    uint256 amount,
    uint256 maxSharesOut
) public payable virtual override returns (uint256 sharesOut) {

    ERC20(address(vault)).safeApprove(address(vault), amount);
    if ((sharesOut = vault.withdraw(amount, to, msg.sender)) > maxSharesOut) {
        revert MaxSharesError();
    }
}

function withdraw(uint256 amount) external {
    require(msg.sender == owner());
    ERC20(asset()).safeTransferFrom(address(this), msg.sender, amount);
}
```

## Proof of Concept

Please add the following test in `src\test\AstariaTest.t.sol`. This test will pass to demonstrate the described scenario.

```solidity
function testPrivateVaultStrategistIsUnableToWithdraw() public {
    uint256 amountToLend = 50 ether;
    vm.deal(strategistOne, amountToLend);

    address privateVault = _createPrivateVault({
        strategist: strategistOne,
        delegate: strategistTwo
    });

    vm.startPrank(strategistOne);

    WETH9.deposit{value: amountToLend}();
    WETH9.approve(privateVault, amountToLend);

    // strategistOne deposits 50 ether WETH to privateVault
    Vault(privateVault).deposit(amountToLend, strategistOne);

    // calling router's withdraw function for withdrawing assets from privateVault reverts
    vm.expectRevert(bytes("APPROVE_FAILED"));
    ASTARIA_ROUTER.withdraw(
        IERC4626(privateVault),
        strategistOne,
        amountToLend,
        type(uint256).max
    );

    // directly withdrawing various asset amounts from privateVault also fails
    vm.expectRevert(bytes("TRANSFER_FROM_FAILED"));
    Vault(privateVault).withdraw(amountToLend);

    vm.expectRevert(bytes("TRANSFER_FROM_FAILED"));
    Vault(privateVault).withdraw(1);

    vm.stopPrank();
}
```

## Recommendation

<https://github.com/code-423n4/2023-01-astaria/blob/main/src/Vault.sol#L72> can be updated to the following code.

```solidity
ERC20(asset()).safeTransfer(msg.sender, amount);
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way the router and the vault handle ERC20 allowances when withdrawing assets from a private vault. The router’s withdraw function first calls safeApprove on the vault contract, assuming the vault implements the standard ERC20 approve interface. Private vault implementations, however, deliberately omit an approve function, causing the approve call to revert with an APPROVE_FAILED error. Even if the router call is bypassed, the vault’s own withdraw implementation uses safeTransferFrom to move the underlying asset token from the vault to the caller. safeTransferFrom requires the vault to have an allowance set for itself, but because the vault cannot approve itself, the transferFrom call fails and reverts with TRANSFER_FROM_FAILED. As a result, after a strategist deposits an asset token such as WETH into a private vault, any subsequent attempt to withdraw that deposit – either through the router or directly via the vault – fails, leaving the funds locked inside the vault. This situation occurs only for private vaults that lack an approve implementation; public vaults that provide approve work as expected, making the bug easy to miss during casual testing. The issue was discovered during a formal audit by Code4rena, which added a test reproducing the failure and observed the specific revert messages. From a user’s perspective the symptom is a silent loss of the expected balance: the user sees the transaction revert, receives no tokens, and the deposited amount remains inaccessible, violating the expectation that a deposited asset can be withdrawn on demand. The root cause is a misuse of the ERC20 allowance pattern – the contract assumes it can grant itself permission to move its own tokens, which is not possible without an approve function. This class of bug can be described as an allowance‑misconfiguration or missing self‑approval in token handling. To remediate the issue the vault’s withdraw logic should be changed to use safeTransfer instead of safeTransferFrom, eliminating the need for an allowance, and the router should avoid calling approve on vaults that do not implement it. By correcting the token transfer method, the protocol restores the fundamental accounting invariant that deposited assets remain fully recoverable by the rightful owner.
