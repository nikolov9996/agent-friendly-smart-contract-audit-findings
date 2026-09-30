---
id: 23433
severity: "High"
---

# Withdrawers of sUSDe always incur a loss because parameters passed from Tranche::_withdraw to CDO::withdraw are inverted

## Description

Users can choose to withdraw either sUSDe or USDe. The system is in charge of making the proper calculations to determine how much USDe value will be withdrawn based on the requested asset and the tokenAmount of such an asset. Based on the calculated USDe value being withdrawn, the system burns the required TrancheShares for that amount of USDe being withdrawn from the system.  
This issue reports a problem in which the Tranche::_withdraw passes two parameters in the inverse order to the CDO::withdraw. These parameters are baseAssets and tokenAssets. The CDO expects to receive tokenAssets first and then baseAssets, but the Tranche passes baseAssets first and then tokenAssets.  

The parameters in the inverse order make the system do calculations with the wrong amounts, resulting (on the Strategy contract) that the amount of sUSDe to release to the user is way lower than what it should be (especially when the sUSDe <=> USDe rate is high).

```solidity
// Tranche::_withdraw() //
function _withdraw(
    address token,
    address caller,
    address receiver,
    address owner,
    uint256 baseAssets,
    uint256 tokenAssets,
    uint256 shares
) internal virtual {
    ...
    //@audit => Burn Trancheshares for the full requested sUSDe
    @> _burn(owner, shares);
    //@audit-issue => Sends baseAssets first and then tokenAssets
    @> cdo.withdraw(address(this), token, baseAssets, tokenAssets, receiver);
    ...
}
```

```solidity
// StrataCDO::withdraw() //
function withdraw(address tranche, address token, uint256 tokenAmount, uint256 baseAssets, address receiver) external onlyTranche nonReentrant {
    ...
    //@audit => Because of the inverted parameters `tokenAmount` is actually `baseAssets`, and `baseAssets` is actually `tokenAssets`,
    @> strategy.withdraw(tranche, token, tokenAmount, baseAssets, receiver);
    ...
}
```

```solidity
// Strategy::withdraw() //
function withdraw (address tranche, address token, uint256 tokenAmount, uint256 baseAssets, address receiver) external onlyCDO returns (uint256) {
    //@audit => `baseAssets` should represent amount of `USDe` being withdrawn, but, because of the inverted parameters, here represents the actual requested amount of `sUSDe` to withdraw,
    uint256 shares = sUSDe.previewWithdraw(baseAssets);
    if (token == address(sUSDe)) {
        uint256 cooldownSeconds = cdo.isJrt (tranche) ? sUSDeCooldownJrt : sUSDeCooldownSrt;
        //@audit => transfers calculates `shares` of `sUSDe` to Cooldown to be sent to the user after cooldown.
        erc20Cooldown.transfer(sUSDe, receiver, shares, cooldownSeconds);
        return shares;
    }
    ...
}
```

Impact: Withdrawers will always incur a loss in USDe value because more TrancheShares are burned compared to the received value in USDe terms.

## Proof of Concept

```solidity
function test_WithdrawingsUSDECausesLosesForUsers() public {
    address bob = makeAddr("Bob");
    USDe.mint(bob, 1000 ether);
    vm.startPrank(bob);
    //@audit => Bob initializes the exchange rate on sUSDe
    USDe.approve(address(sUSDe), type(uint256).max);
    sUSDe.deposit(1000 ether, bob);
    vm.stopPrank();
    address alice = makeAddr("Alice");
    uint256 initialDeposit = 150 ether;
    USDe.mint(alice, initialDeposit);
    //@audit-info => There are 1k sUSDe in circulation and 1k USDe deposited on the sUSDe contract
    //@audit-info => Exchange Rate is 1:1
    assertEq(USDe.balanceOf(address(sUSDe)), 1000 ether);
    assertEq(sUSDe.totalSupply(), 1000 ether);
    assertEq(sUSDe.convertToAssets(1e18), 1e18);
    // Simulate yield by adding USDe directly to sUSDe contract
    //@audit-info => Set sUSDe exchange rate to USDe (1:1.5)
    USDe.mint(address(sUSDe), 500 ether); // 50% yield
    assertApproxEqAbs(sUSDe.convertToAssets(1e18), 1.5e18, 1e6);
    //@audit-info => Bob deposits sUSDe when sUSDE rate to USDe is 1:1.5
    vm.startPrank(bob);
    sUSDe.approve(address(jrtVault), type(uint256).max);
    jrtVault.deposit(address(sUSDe), 100e18, bob);
    assertApproxEqAbs(jrtVault.balanceOf(bob), 150e18, 1e6);
    vm.stopPrank();
    vm.startPrank(alice);
    //@audit => Alice gets 100 sUSDe by staking 150 USDe
    USDe.approve(address(sUSDe), type(uint256).max);
    sUSDe.deposit(150e18, alice);
    assertApproxEqAbs(sUSDe.balanceOf(alice), 100e18, 1e6);
    //@audit => Alice deposits 100 sUSDe on the JRTranche and gets 150 JRTrancheShares
    sUSDe.approve(address(jrtVault), type(uint256).max);
    jrtVault.deposit(address(sUSDe), 100e18, alice);
    assertApproxEqAbs(jrtVault.balanceOf(alice), 150e18, 1e6);
    assertEq(sUSDe.balanceOf(alice), 0);
    //@audit-info => Requests to withdraw 100e18 sUSDe which are worth 150 USDe
    uint256 expected_sUSDeWithdrawn = 100e18;
    uint256 expected_USDe_valueWithdrawn = sUSDe.convertToAssets(expected_sUSDeWithdrawn);
    //@audit-issue => Alice withdraws 100 sUSDe but gets only ~66.6 sUSDe, all her JRTrancheShares are burnt,
    jrtVault.withdraw(address(sUSDe), expected_sUSDeWithdrawn, alice, alice);
    uint256 alice_actual_sUSDeBalance = sUSDe.balanceOf(alice);
    uint256 alice_USDe_actualWithdrawn = sUSDe.convertToAssets(alice_actual_sUSDeBalance);
    assertEq(jrtVault.balanceOf(alice), 0);
    assertApproxEqAbs(alice_actual_sUSDeBalance, 66.5e18, 1e18);
    console2.log("Alice expected withdrawn sUSDe: ", expected_sUSDeWithdrawn);
    console2.log("Alice actual withdrawn sUSDe: ", alice_actual_sUSDeBalance);
    console2.log("====");
    console2.log("Alice expected withdrawn USDe value: ", expected_USDe_valueWithdrawn);
    console2.log("Alice actual withdrawn USDe value: ", alice_USDe_actualWithdrawn);
    vm.stopPrank();
}
```

## Recommendation

Recommended Mitigation: On the Tranche::_withdraw, make sure to pass the parameters in the correct order when calling the CDO::withdraw  

```solidity
function _withdraw(
    address token,
    address caller,
    address receiver,
    address owner,
    uint256 baseAssets,
    uint256 tokenAssets,
    uint256 shares
) internal virtual {
    ...
    // - cdo.withdraw(address(this), token, baseAssets, tokenAssets, receiver);
    + cdo.withdraw(address(this), token, tokenAssets, baseAssets, receiver);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an argument‑order inversion that causes every sUSDe withdrawal to lose value. In the internal Tranche::_withdraw function the contract forwards two numeric values to the CDO::withdraw function: baseAssets (the amount of USDe to be withdrawn) and tokenAssets (the amount of sUSDe requested). The CDO contract, however, expects the token amount first and the base assets second. Because the parameters are passed in the opposite order, the downstream Strategy::withdraw routine interprets the USDe amount as the amount of sUSDe to release. It then calls sUSDe.previewWithdraw with this incorrect value, which returns a much smaller share count. The strategy transfers only that reduced number of sUSDe tokens to the user’s cooldown contract, while the Tranche contract still burns the full amount of tranche shares that correspond to the original USDe value. As a result, the user receives far fewer sUSDe tokens than requested, effectively losing USDe value. The bug manifests whenever a user withdraws sUSDe, regardless of the exchange rate, but the financial impact is amplified when the sUSDe‑to‑USDe rate deviates from 1:1 (e.g., a 1:1.5 rate leads to roughly a one‑third payout). The affected parties are any holder of sUSDe who attempts to withdraw, as they see their tranche shares burned and their token balance reduced to an unexpected low amount. The issue was discovered during a security audit by inspecting the call flow between Tranche, CDO, and Strategy contracts and confirming the mismatch with a concrete test case that showed a user receiving ~66 sUSDe instead of the requested 100 sUSDe. The problem is subtle because the function signatures appear correct and the transaction does not revert; it simply performs a wrong calculation, making the loss easy to miss unless balances are compared before and after withdrawal. The bug belongs to the class of “parameter mis‑ordering” or “argument inversion” bugs, which break accounting assumptions and cause funds to disappear from the user’s perspective. To remediate, the Tranche::_withdraw call must be corrected to pass tokenAssets first and baseAssets second, i.e., `cdo.withdraw(address(this), token, tokenAssets, baseAssets, receiver);`. This aligns the data with the CDO interface, restores correct previewWithdraw calculations, ensures the proper amount of sUSDe is transferred, and prevents unnecessary burning of tranche shares.
