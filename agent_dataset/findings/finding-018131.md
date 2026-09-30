---
id: 18131
severity: "High"
---

# SwingTraderManager.addSwingTrader will push traderId with `active = false` to activeTraders

## Description

In SwingTraderManager.addSwingTrader, if `active = false`, the traderId is also pushed to activeTraders.

```solidity
function addSwingTrader(
  uint256 traderId,
  address _swingTrader,
  bool active,
  string calldata name
) external onlyRoleMalt(ADMIN_ROLE, "Must have admin privs") {
  SwingTraderData storage trader = swingTraders[traderId];
  require(traderId > 2 && trader.id == 0, "TraderId already used");
  require(_swingTrader != address(0), "addr(0)");

  swingTraders[traderId] = SwingTraderData({
    id: traderId,
    index: activeTraders.length,
    traderContract: _swingTrader,
    name: name,
    active: active
  });

  activeTraders.push(traderId);

  emit AddSwingTrader(traderId, name, active, _swingTrader);
}
```

Afterwards, if toggleTraderActive is called on the traderId, the traderId will be pushed to activeTraders again.

```solidity
function toggleTraderActive(uint256 traderId)
  external
  onlyRoleMalt(ADMIN_ROLE, "Must have admin privs")
{
  SwingTraderData storage trader = swingTraders[traderId];
  require(trader.id == traderId, "Unknown trader");

  bool active = !trader.active;
  trader.active = active;

  if (active) {
    // setting it to active so add to activeTraders
    trader.index = activeTraders.length;
    activeTraders.push(traderId);
  } else {
    // Becoming inactive so remove from activePools
    uint256 index = trader.index;
    uint256 lastTrader = activeTraders[activeTraders.length - 1];

    activeTraders[index] = lastTrader;
    activeTraders.pop();

    swingTraders[lastTrader].index = index;
    trader.index = 0;
  }
}
```

This means that in `getTokenBalances()/calculateSwingTraderMaltRatio()`, since there are two identical traderIds in activeTraders, the data in this trader will be calculated twice.

Wrong `getTokenBalances()` will result in wrong data when `syncGlobalCollateral()`.

```solidity
function getTokenBalances()
  external
  view
  returns (uint256 maltBalance, uint256 collateralBalance)
{
  uint256[] memory traderIds = activeTraders;
  uint256 length = traderIds.length;

  for (uint256 i; i < length; ++i) {
    SwingTraderData memory trader = swingTraders[activeTraders[i]];
    maltBalance += malt.balanceOf(trader.traderContract);
    collateralBalance += collateralToken.balanceOf(trader.traderContract);
  }
}
```

Wrong `calculateSwingTraderMaltRatio()` will cause `MaltDataLab.getRealBurnBudget()/getSwingTraderEntryPrice()` to be wrong.

```solidity
function calculateSwingTraderMaltRatio()
  public
  view
  returns (uint256 maltRatio)
{
  uint256[] memory traderIds = activeTraders;
  uint256 length = traderIds.length;
  uint256 decimals = collateralToken.decimals();
  uint256 maltDecimals = malt.decimals();
  uint256 totalMaltBalance;
  uint256 totalCollateralBalance;

  for (uint256 i; i < length; ++i) {
    SwingTraderData memory trader = swingTraders[activeTraders[i]];
    totalMaltBalance += malt.balanceOf(trader.traderContract);
    totalCollateralBalance += collateralToken.balanceOf(
      trader.traderContract
    );
  }

  totalMaltBalance = maltDataLab.maltToRewardDecimals(totalMaltBalance);

  uint256 stMaltValue = ((totalMaltBalance * maltDataLab.priceTarget()) /
    (10**decimals));

  uint256 netBalance = totalCollateralBalance + stMaltValue;

  if (netBalance > 0) {
    maltRatio = ((stMaltValue * (10**decimals)) / netBalance);
  } else {
    maltRatio = 0;
  }
}
```

What’s more serious is that even if toggleTraderActive is called again, only one traderId will pop up from activeTraders, and the other traderId cannot be popped up.

This causes the trade to participate in the calculation of `getTokenBalances()/calculateSwingTraderMaltRatio()` even if the trade is deactive.

Considering that the active parameter is likely to be false when addSwingTrader is called and cannot be recovered, this vulnerability should be High risk.

## Proof of Concept

```solidity
function testAddSwingTrader(address newSwingTrader) public {
  _setupContract();
  vm.assume(newSwingTrader != address(0));
  vm.prank(admin);
  swingTraderManager.addSwingTrader(3, newSwingTrader, false, "Test");

  (
    uint256 id,
    uint256 index,
    address traderContract,
    string memory name,
    bool active
  ) = swingTraderManager.swingTraders(3);

  assertEq(id, 3);
  assertEq(index, 2);
  assertEq(traderContract, newSwingTrader);
  assertEq(name, "Test");
  assertEq(active, false);
  vm.prank(admin);
  swingTraderManager.toggleTraderActive(3);
  assertEq(swingTraderManager.activeTraders(2),3);
  assertEq(swingTraderManager.activeTraders(3),3); // @audit:activeTraders[2] = activeTraders[3] = 3
  vm.prank(admin);
  swingTraderManager.toggleTraderActive(3);
  assertEq(swingTraderManager.activeTraders(2),3);
}
```

## Recommendation

Change to:

```solidity
function addSwingTrader(
  uint256 traderId,
  address _swingTrader,
  bool active,
  string calldata name
) external onlyRoleMalt(ADMIN_ROLE, "Must have admin privs") {
  SwingTraderData storage trader = swingTraders[traderId];
  require(traderId > 2 && trader.id == 0, "TraderId already used");
  require(_swingTrader != address(0), "addr(0)");

  swingTraders[traderId] = SwingTraderData({
    id: traderId,
    index: active ? activeTraders.length : 0,
    traderContract: _swingTrader,
    name: name,
    active: active
  });
  if(active) activeTraders.push(traderId);

  emit AddSwingTrader(traderId, name, active, _swingTrader);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract allows an administrator to register a new swing trader through addSwingTrader. When the active flag is set to false, the function still pushes the trader identifier into the activeTraders array, which is intended to contain only currently active traders. As a result the same traderId can appear multiple times in activeTraders – once when it is added while inactive and again when it is later toggled to active. The toggleTraderActive function updates the index and removes a single occurrence when a trader is deactivated, but it does not remove the duplicate entry that was created earlier. Consequently, any routine that iterates over activeTraders, such as getTokenBalances and calculateSwingTraderMaltRatio, will count the balances of that trader twice. This double‑counting inflates the reported malt and collateral totals, leading to an incorrect malt‑to‑collateral ratio, wrong reward calculations, and erroneous global collateral synchronization. From a user perspective the protocol may display higher token balances than actually exist, reward calculations may appear overly generous, or fees may be mis‑applied, creating a mismatch between expected and real outcomes. The flaw originates from a logic error in the management of the activeTraders list – the condition that decides whether to push an identifier does not consider the active flag, and the removal logic assumes a one‑to‑one relationship between traders and list entries. The issue was uncovered during a security audit that exercised the addSwingTrader and toggleTraderActive functions with inactive traders and observed duplicate entries. It can be difficult to notice because the trader’s active state flag reports correctly, while the underlying array silently contains duplicates, so UI components that rely on the flag remain consistent. The vulnerability belongs to the class of state‑inconsistency bugs where a collection meant to reflect a boolean status becomes desynchronized, leading to accounting errors. To remediate, the contract should only push a traderId into activeTraders when the active flag is true, set the index appropriately only for active entries, and ensure that deactivation removes all occurrences of the identifier. Proper checks and safeguards around list management will restore the invariant that activeTraders contains a unique set of currently active traders, preventing double counting and preserving correct financial calculations.
