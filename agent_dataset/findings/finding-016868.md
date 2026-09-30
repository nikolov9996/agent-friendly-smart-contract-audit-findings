---
id: 16868
severity: "High"
---

# Users who deposit in one vault can lose all deposits and receive nothing when counterparty vault has no deposits

## Description

For a market, if users only deposit in the hedge vault or only deposit in the risk vault but not in both, then these users will lose their deposits and receive nothing when they call the following `withdraw` function after the depeg event occurs.

If the vault that has deposits is called Vault A, and the counterparty vault that has no deposit is called Vault B, then:

  * As shown by the `triggerDepeg` function below, when executing `insrVault.sendTokens(epochEnd, address(riskVault))` and `riskVault.sendTokens(epochEnd, address(insrVault))`, the deposits of Vault A are transferred to Vault B but nothing is transferred to Vault A since Vault B has no deposit;
  * When `triggerDepeg` executes `insrVault.setClaimTVL(epochEnd, riskVault.idFinalTVL(epochEnd))` and `riskVault.setClaimTVL(epochEnd, insrVault.idFinalTVL(epochEnd))`, Vault B’s `idClaimTVL[id]` is set to Vault A’s `idFinalTVL(epochEnd))` but Vault A’s `idClaimTVL[id]` is set to 0 because Vault B’s `idFinalTVL(epochEnd)` is 0.

Because of these, calling the `beforeWithdraw` function below will return a 0 `entitledAmount`, and calling `withdraw` then transfers that 0 amount to the user who has deposited. As a result, these users’ deposits are transferred to the counterparty vault, and they receive nothing at all.

```solidity
function triggerDepeg(uint256 marketIndex, uint256 epochEnd)
    public
    isDisaster(marketIndex, epochEnd)
{
    address[] memory vaultsAddress = vaultFactory.getVaults(marketIndex);
    Vault insrVault = Vault(vaultsAddress[0]);
    Vault riskVault = Vault(vaultsAddress[1]);

    //require this function cannot be called twice in the same epoch for the same vault
    if(insrVault.idFinalTVL(epochEnd) != 0)
        revert NotZeroTVL();
    if(riskVault.idFinalTVL(epochEnd) != 0) 
        revert NotZeroTVL();

    insrVault.endEpoch(epochEnd, true);
    riskVault.endEpoch(epochEnd, true);

    insrVault.setClaimTVL(epochEnd, riskVault.idFinalTVL(epochEnd));
    riskVault.setClaimTVL(epochEnd, insrVault.idFinalTVL(epochEnd));

    insrVault.sendTokens(epochEnd, address(riskVault));
    riskVault.sendTokens(epochEnd, address(insrVault));

    VaultTVL memory tvl = VaultTVL(
        riskVault.idClaimTVL(epochEnd),
        insrVault.idClaimTVL(epochEnd),
        riskVault.idFinalTVL(epochEnd),
        insrVault.idFinalTVL(epochEnd)
    );

    emit DepegInsurance(
        keccak256(
            abi.encodePacked(
                marketIndex,
                insrVault.idEpochBegin(epochEnd),
                epochEnd
            )
        ),
        tvl,
        true,
        epochEnd,
        block.timestamp,
        getLatestPrice(insrVault.tokenInsured())
    );
}

function setClaimTVL(uint256 id, uint256 claimTVL) public onlyController {
    idClaimTVL[id] = claimTVL;
}

function withdraw(
    uint256 id,
    uint256 assets,
    address receiver,
    address owner
)
    external
    override
    epochHasEnded(id)
    marketExists(id)
    returns (uint256 shares)
{
    if(
        msg.sender != owner &&
        isApprovedForAll(owner, receiver) == false)
        revert OwnerDidNotAuthorize(msg.sender, owner);

    shares = previewWithdraw(id, assets); // No need to check for rounding error, previewWithdraw rounds up.

    uint256 entitledShares = beforeWithdraw(id, shares);
    _burn(owner, id, shares);

    //Taking fee from the amount
    uint256 feeValue = calculateWithdrawalFeeValue(entitledShares, id);
    entitledShares = entitledShares - feeValue;
    asset.transfer(treasury, feeValue);

    emit Withdraw(msg.sender, receiver, owner, id, assets, entitledShares);
    asset.transfer(receiver, entitledShares);

    return entitledShares;
}

function beforeWithdraw(uint256 id, uint256 amount)
    public
    view
    returns (uint256 entitledAmount)
{
    // in case the risk wins aka no depeg event
    // risk users can withdraw the hedge (that is paid by the hedge buyers) and risk; withdraw = (risk + hedge)
    // hedge pay for each hedge seller = ( risk / tvl before the hedge payouts ) * tvl in hedge pool
    // in case there is a depeg event, the risk users can only withdraw the hedge
    if (
        keccak256(abi.encodePacked(symbol)) ==
        keccak256(abi.encodePacked("rY2K"))
    ) {
        if (!idDepegged[id]) {
            //depeg event did not happen
            /*
            entitledAmount =
                (amount / idFinalTVL[id]) *
                idClaimTVL[id] +
                amount;
            */
            entitledAmount =
                amount.divWadDown(idFinalTVL[id]).mulDivDown(
                    idClaimTVL[id],
                    1 ether
                ) +
                amount;
        } else {
            //depeg event did happen
            entitledAmount = amount.divWadDown(idFinalTVL[id]).mulDivDown(
                idClaimTVL[id],
                1 ether
            );
        }
    }
    // in case the hedge wins aka depegging
    // hedge users pay the hedge to risk users anyway,
    // hedge guy can withdraw risk (that is transfered from the risk pool),
    // withdraw = % tvl that hedge buyer owns
    // otherwise hedge users cannot withdraw any Eth
    else {
        entitledAmount = amount.divWadDown(idFinalTVL[id]).mulDivDown(
            idClaimTVL[id],
            1 ether
        );
    }

    return entitledAmount;
}
```

## Proof of Concept

Please append the following tests in `test\AssertTest.t.sol`. These tests will pass to demonstrate the described scenarios.

```solidity
function testWithdrawFromRiskAfterDepegWhenThereIsNoCounterparty() public {
    vm.deal(chad, AMOUNT * CHAD_MULTIPLIER);

    vm.startPrank(admin);
    FakeOracle fakeOracle = new FakeOracle(oracleFRAX, STRIKE_PRICE_FAKE_ORACLE);
    vaultFactory.createNewMarket(FEE, tokenFRAX, DEPEG_AAA, beginEpoch, endEpoch, address(fakeOracle), "y2kFRAX_99*");
    vm.stopPrank();

    address hedge = vaultFactory.getVaults(1)[0];
    address risk = vaultFactory.getVaults(1)[1];
    
    Vault vHedge = Vault(hedge);
    Vault vRisk = Vault(risk);

    // chad deposits in risk vault, and no one deposits in hedge vault
    vm.startPrank(chad);
    ERC20(WETH).approve(risk, AMOUNT * CHAD_MULTIPLIER);
    vRisk.depositETH{value: AMOUNT * CHAD_MULTIPLIER}(endEpoch, chad);

    assertTrue(vRisk.balanceOf(chad,endEpoch) == (AMOUNT * CHAD_MULTIPLIER));
    vm.stopPrank();

    vm.warp(beginEpoch + 10 days);

    // depeg occurs
    controller.triggerDepeg(SINGLE_MARKET_INDEX, endEpoch);

    vm.startPrank(chad);

    // chad withdraws from risk vault
    uint256 assets = vRisk.balanceOf(chad,endEpoch);
    vRisk.withdraw(endEpoch, assets, chad, chad);

    assertTrue(vRisk.balanceOf(chad,endEpoch) == NULL_BALANCE);
    uint256 entitledShares = vRisk.beforeWithdraw(endEpoch, assets);
    assertTrue(entitledShares - vRisk.calculateWithdrawalFeeValue(entitledShares,endEpoch) == ERC20(WETH).balanceOf(chad));

    // chad receives nothing
    assertEq(entitledShares, 0);
    assertEq(ERC20(WETH).balanceOf(chad), 0);

    vm.stopPrank();
}

function testWithdrawFromHedgeAfterDepegWhenThereIsNoCounterparty() public {
    vm.deal(alice, AMOUNT);

    vm.startPrank(admin);
    FakeOracle fakeOracle = new FakeOracle(oracleFRAX, STRIKE_PRICE_FAKE_ORACLE);
    vaultFactory.createNewMarket(FEE, tokenFRAX, DEPEG_AAA, beginEpoch, endEpoch, address(fakeOracle), "y2kFRAX_99*");
    vm.stopPrank();

    address hedge = vaultFactory.getVaults(1)[0];
    address risk = vaultFactory.getVaults(1)[1];
    
    Vault vHedge = Vault(hedge);
    Vault vRisk = Vault(risk);

    // alice deposits in hedge vault, and no one deposits in risk vault
    vm.startPrank(alice);
    ERC20(WETH).approve(hedge, AMOUNT);
    vHedge.depositETH{value: AMOUNT}(endEpoch, alice);

    assertTrue(vHedge.balanceOf(alice,endEpoch) == (AMOUNT));
    vm.stopPrank();

    vm.warp(beginEpoch + 10 days);

    // depeg occurs
    controller.triggerDepeg(SINGLE_MARKET_INDEX, endEpoch);

    vm.startPrank(alice);

    // alice withdraws from hedge vault
    uint256 assets = vHedge.balanceOf(alice,endEpoch);
    vHedge.withdraw(endEpoch, assets, alice, alice);

    assertTrue(vHedge.balanceOf(alice,endEpoch) == NULL_BALANCE);
    uint256 entitledShares = vHedge.beforeWithdraw(endEpoch, assets);
    assertTrue(entitledShares - vHedge.calculateWithdrawalFeeValue(entitledShares,endEpoch) == ERC20(WETH).balanceOf(alice));
    
    // alice receives nothing
    assertEq(entitledShares, 0);
    assertEq(ERC20(WETH).balanceOf(alice), 0);

    vm.stopPrank();
}
```

## Recommendation

When users only deposit in one vault, and no one deposits in the counterparty vault, the insurance practice of hedging and risking actually does not exist. In this situation, after the epoch is started, the users, who have deposited, should be allowed to withdraw their full deposit amounts.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability arises in a dual‑vault hedging market where users can deposit into either a hedge vault (Vault A) or a risk vault (Vault B). The protocol assumes that both vaults contain deposits so that, when a depeg event is triggered, each vault can transfer its assets to its counter‑party and then calculate a claim TVL (total value locked) for withdrawals. If, however, only one side holds deposits and the opposite vault is empty, the depeg routine still executes the token transfer and claim TVL assignment. Specifically, the `triggerDepeg` function calls `sendTokens` for both vaults, moving the deposits of the populated vault to the empty vault, while the empty vault sends no assets back. Afterwards, the function sets the `idClaimTVL` of each vault to the `idFinalTVL` of its counterpart. Because the empty vault’s final TVL is zero, the populated vault ends up with a claim TVL of zero. When a user later invokes `withdraw`, the `beforeWithdraw` helper computes the entitled amount based on the ratio `amount / idFinalTVL * idClaimTVL`. With `idClaimTVL` equal to zero, this calculation returns zero, so the user receives no funds even though their deposit was previously transferred to the opposite vault. From the user’s perspective the balance shown after withdrawal is zero and no assets are received, contradicting the expectation that they should be able to withdraw at least their original deposit. The bug surfaces only after a depeg event and only when one side of the market is unpopulated; under normal operation with both vaults funded the calculations produce correct amounts. The issue was uncovered during a Code4rena audit by analysing the depeg logic and observing that the claim TVL assignment does not handle the edge case of an empty counter‑party vault. It can be difficult to notice because the code path is exercised only in a specific market state, and the arithmetic itself appears sound for regular cases. The underlying class of bug is an asymmetric accounting error: the protocol’s settlement logic assumes symmetric participation and fails to guard against a zero‑claim scenario, leading to a “zero‑claim” loss of funds. To remediate the problem the contract should detect when the counterpart vault has a zero final TVL and either skip the token transfer or set the claim TVL of the populated vault to its own final TVL, thereby allowing users to withdraw their full deposits. Alternatively, the protocol could enforce a minimum deposit in both vaults before allowing a depeg, or provide a fallback withdrawal path that returns the original assets when the counterpart is empty. Fixing this logic restores the intended business rule that users can always retrieve their funds, even if the hedging side is unfilled, and eliminates the scenario where deposits disappear without compensation.
