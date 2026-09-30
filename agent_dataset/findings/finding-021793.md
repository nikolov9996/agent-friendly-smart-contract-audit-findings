---
id: 21793
severity: "High"
---

# Incorrect percentage calculation in NukeFund and EntityForging when `taxCut` is changed from default value

## Description

In both `NukeFund::receive` and `EntityForging::forgeWithListed`, if the owner changes `taxCut` from its default value of 10, the percentage calculations for fee distribution become severely inaccurate. This flaw can lead to:

  1. Incorrect distribution of funds between developers, users, and the protocol.
  2. Potential for significant financial losses or unintended gains.
  3. Undermining of the protocol’s economic model.
  4. Loss of user trust if discrepancies are noticed.

The root cause is the use of simple division instead of proper percentage calculation:
```solidity
    // NukeFund
    uint256 devShare = msg.value / taxCut; // Calculate developer's share (10%)
    uint256 remainingFund = msg.value - devShare; // Calculate remaining funds to add to the fund

    // EntityForging
    uint256 devFee = forgingFee / taxCut;
    uint256 forgerShare = forgingFee - devFee;
```
Some mathematical examples:

  * When `taxCut = 10`, `1/10 = 0.1 = 10%` (correct).
  * When `taxCut = 5`, `1/5 = 0.2 = 20%` (intended 5%, actually 20%).
  * When `taxCut = 20`, `1/20 = 0.05 = 5%` (intended 20%, actually 5%).

## Proof of Concept

This is a test for the `NukeFund`, EntityForging is the same scenario just longer so I chose to send you the more concise test. We are going to set the `taxCut` to 5:
```solidity
        function test_FundsRoundWrong() public {
            nukeFund.setTaxCut(5);
            uint256 devShare = 0.05 ether;
            uint256 initialDevBalance = nukeFund.devAddress().balance;
            uint256 initialNukeFund = nukeFund.getFundBalance();

            vm.prank(user1);
            
            address(nukeFund).call{value: 1 ether}("");

            uint256 finalDevBalance = nukeFund.devAddress().balance;
            uint256 devGained = finalDevBalance - initialDevBalance;

            console.log("Dev Balance Gained:", devGained);

            assertNotEq(address(nukeFund).balance, initialNukeFund + 0.95 ether);

            uint256 devBalance = nukeFund.devAddress().balance;

            assertNotEq(devBalance, initialDevBalance + devShare);
        }
```
You can clearly see when it’s supposed to be “5%” tax, it’s instead 20%, leading the dev to get `2e17` of the `1e18` and the `NukeFund` getting `8e17`.

## Recommendation

Implement a basis point (BPS) system for precise percentage calculations. This means now that with a BPS value of `10_000` you would represent 10% as `1000` and 5% in our tests as `500`.

Add the following changes:

  1. At the top of `EntityForging` and `NukeFund` where state variables reside, add the following BPS state variable and change default `taxCut` of 10% to correspond to the BPS values:

    +  uint256 private constant BPS = 10_000;
    -  uint256 public taxCut = 10;
    +  uint256 public taxCut = 10_000;

  2. Update the calculations in `EntityForging` and `NukeFund` where `taxCut` is used.

```solidity
    // NukeFund 
-    uint256 devShare = msg.value / taxCut; // Calculate developer's share (10%)
+    uint256 devShare = (msg.value * taxCut) / BPS;

    // EntityForging
-    uint256 devFee = forgingFee / taxCut;
+    uint256 devShare = (msg.value * taxCut) / BPS;
```

  3. Also consider adding a boundary `setTaxCut` to make sure `taxCut` isn’t greater than `BPS`:

```solidity
  function setTaxCut(uint256 _taxCut) external onlyOwner {
+    require(_taxCut <= BPS, "Tax cut cannot exceed 100%");
    taxCut = _taxCut;
  }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract implements a configurable taxCut parameter that determines what fraction of incoming ether is taken as a developer fee before the remainder is added to the protocol fund. The code calculates the fee by dividing the incoming amount by the taxCut value (e.g., devShare = msg.value / taxCut). This approach only yields the correct percentage when taxCut is set to its default of 10, because 1/10 equals 10 %. When the owner changes taxCut to any other integer, the division produces a completely different proportion: a taxCut of 5 results in a 20 % fee, and a taxCut of 20 results in a 5 % fee. The root cause is the misuse of integer division as a percentage operator instead of multiplying by the percentage and dividing by a fixed denominator (basis points). The vulnerability is triggered whenever the public setter for taxCut is called with a value different from the default, which is allowed without validation. An attacker or a careless owner can set taxCut to a small number, causing the developer share to be dramatically larger than intended while the protocol fund receives a smaller amount. From a user’s perspective, a sender expects to transfer 1 ether and see roughly 0.95 ether added to the fund (for a 5 % tax), but instead only 0.80 ether is added and the developer address receives 0.20 ether, i.e., the user sees an unexpected large deduction and the protocol balance appears lower than expected. This breaks the economic model, can lead to significant financial loss for users, erodes trust, and constitutes a classic “incorrect percentage calculation” or “mis‑scaled fee computation” bug that violates accounting assumptions. The issue was discovered during a functional test that compared expected and actual balances after setting taxCut to 5; the test showed the developer receiving 20 % instead of the intended 5 %. Because the error is hidden in a simple division expression, it is not obvious from a casual code review and only manifests when the parameter deviates from its default. The recommended remediation is to store percentages in basis points (e.g., 10 % = 1000 bps with a constant BPS = 10_000) and compute fees as (amount * taxCut) / BPS, together with a guard that taxCut never exceeds BPS. This change restores the intended proportional distribution and prevents the developer from receiving unintended excess fees.
